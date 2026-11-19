FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8080

# Cloud Run injects PORT; use shell form so $PORT is expanded at runtime
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
