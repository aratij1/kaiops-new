from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.resilience import CircuitOpenError


@dataclass(frozen=True, slots=True)
class ErrorDescriptor:
    code: str
    message: str
    retryable: bool = False
    category: str = "application"


def request_trace_id(request: Request) -> str:
    """Return the request correlation identifier without trusting empty headers."""
    existing = str(getattr(request.state, "trace_id", "") or "").strip()
    header = str(request.headers.get("x-trace-id") or "").strip()
    trace_id = existing or header or uuid4().hex
    request.state.trace_id = trace_id
    return trace_id


def error_response_payload(
    request: Request,
    descriptor: ErrorDescriptor,
    *,
    detail: Any | None = None,
    validation_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the versioned error contract while retaining FastAPI's detail key."""
    trace_id = request_trace_id(request)
    public_detail = descriptor.message if detail is None else detail
    payload: dict[str, Any] = {
        "detail": public_detail,
        "trace_id": trace_id,
        "error": {
            "contract_version": "kaiops.error.v1",
            "code": descriptor.code,
            "message": descriptor.message,
            "category": descriptor.category,
            "retryable": descriptor.retryable,
            "trace_id": trace_id,
        },
    }
    if validation_errors:
        payload["error"]["validation_errors"] = validation_errors
    return payload


def safe_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose actionable locations and messages but never rejected input values."""
    return [
        {
            "location": [str(part) for part in item.get("loc", ())],
            "message": str(item.get("msg") or "Invalid value"),
            "type": str(item.get("type") or "validation_error"),
        }
        for item in errors
    ]


def install_exception_handlers(app: FastAPI, logger: logging.Logger) -> None:
    """Install one error contract across every service created by common.service."""

    @app.exception_handler(RequestValidationError)
    async def request_validation_failed(request: Request, exc: RequestValidationError) -> JSONResponse:
        descriptor = ErrorDescriptor(
            code="request_validation_failed",
            message="The request did not satisfy the endpoint contract.",
            category="validation",
        )
        return JSONResponse(
            status_code=422,
            headers={"x-trace-id": request_trace_id(request)},
            content=error_response_payload(
                request,
                descriptor,
                detail="Request validation failed",
                validation_errors=safe_validation_errors(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handled_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        structured_detail = exc.detail if isinstance(exc.detail, dict) else {}
        retryable = exc.status_code in {408, 425, 429, 502, 503, 504} or structured_detail.get("retryable") is True
        message = (
            str(exc.detail)
            if isinstance(exc.detail, str)
            else str(structured_detail.get("message") or "The request could not be completed.")
        )
        descriptor = ErrorDescriptor(
            code=str(structured_detail.get("code") or f"http_{exc.status_code}"),
            message=message,
            retryable=retryable,
            category="downstream" if exc.status_code >= 500 else "request",
        )
        headers = dict(exc.headers or {})
        headers["x-trace-id"] = request_trace_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content=error_response_payload(request, descriptor, detail=exc.detail),
        )

    @app.exception_handler(CircuitOpenError)
    async def database_circuit_open(request: Request, _exc: CircuitOpenError) -> JSONResponse:
        descriptor = ErrorDescriptor(
            code="database_temporarily_unavailable",
            message="The database is recovering. Please retry in a few seconds.",
            retryable=True,
            category="dependency",
        )
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "5", "x-trace-id": request_trace_id(request)},
            content=error_response_payload(request, descriptor),
        )

    @app.exception_handler(Exception)
    async def unhandled_application_error(request: Request, exc: Exception) -> JSONResponse:
        trace_id = request_trace_id(request)
        logger.exception(
            "unhandled_application_error",
            extra={"method": request.method, "path": request.url.path, "trace_id": trace_id},
            exc_info=exc,
        )
        descriptor = ErrorDescriptor(
            code="internal_error",
            message="An unexpected service error occurred.",
            category="internal",
        )
        return JSONResponse(
            status_code=500,
            headers={"x-trace-id": trace_id},
            content=error_response_payload(request, descriptor),
        )


# install_exception_handlers above already keeps a raw exception out of any
# HTTP response. It has no reach into a second, separate path: a background
# message-handler failure (RabbitMQ/Kafka consume_forever) whose text is
# persisted into a durable, operator-visible field -- most notably
# AnalysisRequestRecord.terminal_reason, which the web client reads back
# through a normal successful request and displays verbatim
# (frontend/react/src/domain/analysisRequestStatus.ts). A redelivered event
# hitting a database unique-constraint violation surfaced its raw
# "(raised as a result of Query-invoked autoflush ...) Duplicate entry ..."
# text there in production. This is that second boundary. Callers that need
# the raw text for logging or an internal retry heuristic (e.g. detecting a
# transient dependency failure) must keep using the original exception text
# themselves; this exists only for a value handed to a field an operator or
# end user reads back later.
_HANDLER_FAILURE_CATEGORIES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)duplicate entry|integrityerror|unique constraint|already exists"),
        "A duplicate or conflicting record was detected; this was safely coalesced.",
    ),
    (
        re.compile(r"(?i)connection refused|(?:can'?t|cannot|could not) connect|no route to host|name or service not known|connection reset"),
        "A required downstream service was temporarily unreachable.",
    ),
    (
        re.compile(r"(?i)\btimed? out\b|timeout|deadline exceeded"),
        "The operation exceeded its time budget.",
    ),
    (
        re.compile(r"(?i)unauthorized|forbidden|permission denied|access denied|authentication failed"),
        "The operation was not authorized.",
    ),
    (
        re.compile(r"(?i)validation|invalid payload|malformed"),
        "The message payload failed validation.",
    ),
)


def sanitize_handler_failure_text(raw_text: str, *, default: str = "handler_failed") -> str:
    """A short, generic, safe-to-persist-and-display description of a
    background message-handler failure -- never the raw exception text,
    which can carry SQL fragments, table/column names, connection strings,
    or stack detail. Falls back to `default` (not the raw text) when no
    category matches, so an unrecognized failure still cannot leak detail.
    """
    text = str(raw_text or "").strip()
    if not text:
        return default
    for pattern, message in _HANDLER_FAILURE_CATEGORIES:
        if pattern.search(text):
            return message
    return default
