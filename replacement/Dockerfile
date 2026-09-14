FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY kaims_next ./kaims_next
CMD ["uvicorn", "kaims_next.runtime:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
