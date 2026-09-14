// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useInboxFeed } from "./useInboxFeed";

const empty = { rows: [] as { status: string }[] };
const errorMessage = (_payload: unknown, fallback: string) => fallback;
const response = (status: string) => ({ ok: true, json: async () => ({ data: { rows: [{ status }] } }) });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("live incident inbox", () => {
  it("shows a backend closure after the queue refresh action", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response("investigating")).mockResolvedValueOnce(response("closed"));
    vi.stubGlobal("fetch", fetch);
    const { result, unmount } = renderHook(() => useInboxFeed("/feed?project_id=KaiMS", "token", empty, errorMessage));
    await waitFor(() => expect(result.current.data.rows[0]?.status).toBe("investigating"));
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.data.rows[0]?.status).toBe("closed"));
    expect(fetch.mock.calls[1][0]).toBe("/feed?project_id=KaiMS");
    unmount();
  });

  it("refreshes on the timer and focus and stops after unmount", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockResolvedValue(response("investigating"));
    vi.stubGlobal("fetch", fetch);
    const { result, unmount } = renderHook(() => useInboxFeed("/feed", "token", empty, errorMessage));
    await act(async () => {});
    fetch.mockResolvedValue(response("closed"));
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(result.current.data.rows[0].status).toBe("closed");
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    expect(fetch).toHaveBeenCalledTimes(3);
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); window.dispatchEvent(new Event("focus")); });
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("rejects stale responses after the application filter changes", async () => {
    let finishOld: (value: unknown) => void = () => {};
    const fetch = vi.fn().mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; })).mockResolvedValue(response("closed"));
    vi.stubGlobal("fetch", fetch);
    const { result, rerender, unmount } = renderHook(({ url }) => useInboxFeed(url, "token", empty, errorMessage), { initialProps: { url: "/feed?project_id=old" } });
    rerender({ url: "/feed?project_id=new" });
    await waitFor(() => expect(result.current.data.rows[0]?.status).toBe("closed"));
    await act(async () => { finishOld(response("investigating")); });
    expect(result.current.data.rows[0].status).toBe("closed");
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    unmount();
  });

  it("exposes a failed refresh while retaining the last known rows", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response("closed")).mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({}) });
    vi.stubGlobal("fetch", fetch);
    const { result, unmount } = renderHook(() => useInboxFeed("/feed", "token", empty, errorMessage));
    await waitFor(() => expect(result.current.data.rows[0]?.status).toBe("closed"));
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.error).toContain("503"));
    expect(result.current.data.rows[0].status).toBe("closed");
    unmount();
  });
});


it("coalesces live alert events and picks up correlation without waiting for polling", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response("awaiting_correlation")).mockResolvedValue(response("investigating"));
  vi.stubGlobal("fetch", fetch);
  const { result, unmount } = renderHook(() => useInboxFeed("/feed?record_type=all&project_id=checkout-api", "token", empty, errorMessage));
  await waitFor(() => expect(result.current.data.rows[0]?.status).toBe("awaiting_correlation"));
  act(() => {
    for (let i = 0; i < 5; i++) window.dispatchEvent(new CustomEvent("kaiops:operational-update", { detail: { type: "alert.created" } }));
    window.dispatchEvent(new CustomEvent("kaiops:operational-update", { detail: { type: "incident.status" } }));
  });
  await waitFor(() => expect(result.current.data.rows[0]?.status).toBe("investigating"), { timeout: 6000 });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][0]).toContain("project_id=checkout-api");
  unmount();
}, 10_000);


it("clears the previous application's rows when the new scope fails", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response("old-application"))
    .mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({}) });
  vi.stubGlobal("fetch", fetch);
  const { result, rerender, unmount } = renderHook(({ url }) => useInboxFeed(url, "token", empty, errorMessage), { initialProps: { url: "/feed?project=old" } });
  await waitFor(() => expect(result.current.data.rows).toHaveLength(1));
  rerender({ url: "/feed?project=new" });
  expect(result.current.data.rows).toEqual([]);
  await waitFor(() => expect(result.current.error).toContain("503"));
  expect(result.current.data.rows).toEqual([]);
  unmount();
});

it.each([401, 403])("clears protected rows after authorization fails (%s)", async (status) => {
  const fetch = vi.fn().mockResolvedValueOnce(response("closed"))
    .mockResolvedValueOnce({ ok: false, status, json: async () => ({}) });
  vi.stubGlobal("fetch", fetch);
  const { result, unmount } = renderHook(() => useInboxFeed("/feed", "token", empty, errorMessage));
  await waitFor(() => expect(result.current.data.rows).toHaveLength(1));
  act(() => result.current.refresh());
  await waitFor(() => expect(result.current.error).toContain(String(status)));
  expect(result.current.data.rows).toEqual([]);
  unmount();
});

it("reports a malformed successful response instead of an empty healthy queue", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: { rows: null } }) }));
  const { result, unmount } = renderHook(() => useInboxFeed("/feed", "token", empty, errorMessage));
  await waitFor(() => expect(result.current.error).toContain("invalid page"));
  unmount();
});

it("ends a stalled request and allows a retry", async () => {
  vi.useFakeTimers();
  const fetch = vi.fn().mockImplementationOnce((_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  })).mockResolvedValue(response("closed"));
  vi.stubGlobal("fetch", fetch);
  const { result, unmount } = renderHook(() => useInboxFeed("/feed", "token", empty, errorMessage));
  await act(async () => { await vi.advanceTimersByTimeAsync(45_000); });
  expect(result.current.error).toContain("timed out");
  expect(result.current.loading).toBe(false);
  await act(async () => { result.current.refresh(); });
  expect(result.current.data.rows[0].status).toBe("closed");
  unmount();
});
