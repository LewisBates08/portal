FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-trixie AS runtime
ENV ENVIRONMENT=production PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.lock ./
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home portal
COPY backend/ ./
COPY --from=frontend /build/dist ./static
USER 10001
EXPOSE 8000
ENTRYPOINT ["python", "bootstrap.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "40", "--timeout-keep-alive", "5", "--no-access-log", "--log-level", "warning"]
