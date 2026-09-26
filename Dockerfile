FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Use the same libc and Python ABI for dependency installation and execution.
FROM python:3.13-alpine3.23@sha256:6438599575cca0d1df94aeee0d2ae088d4d8846eab554b2ee7784a3a6df0d516 AS dependencies
WORKDIR /build
COPY backend/requirements.lock ./
RUN python -m venv --without-pip /opt/venv \
    && python -m pip --python /opt/venv/bin/python install --no-cache-dir --only-binary=:all: -r requirements.lock \
    && python -m pip --python /opt/venv/bin/python check

FROM dependencies AS test-tools
RUN python -m pip install --no-cache-dir --target /test-tools pytest httpx

FROM python:3.13-alpine3.23@sha256:6438599575cca0d1df94aeee0d2ae088d4d8846eab554b2ee7784a3a6df0d516 AS application
ENV ENVIRONMENT=production PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DIR=/app/static PATH=/opt/venv/bin:$PATH
WORKDIR /app
RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates \
    && python -m pip uninstall -y pip setuptools wheel \
    && python -c "import ensurepip, pathlib, shutil; shutil.rmtree(pathlib.Path(ensurepip.__file__).parent / '_bundled')" \
    && addgroup -g 10001 portal && adduser -D -u 10001 -G portal portal
COPY --from=dependencies /opt/venv /opt/venv
COPY backend/ ./
COPY --from=frontend /build/dist ./static
USER 10001
EXPOSE 8000
ENTRYPOINT ["python", "bootstrap.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "40", "--timeout-keep-alive", "5", "--no-access-log", "--log-level", "warning"]

# Test tooling is never part of either published image.
FROM application AS test
COPY --from=test-tools /test-tools /test-tools
ENV PYTHONPATH=/test-tools:/app

FROM application AS operations
USER root
RUN apk add --no-cache postgresql17-client
USER 10001

# Keep the default image small; backups explicitly select --target operations.
FROM application AS runtime
