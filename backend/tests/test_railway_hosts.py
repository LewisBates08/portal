"""Railway's healthcheck host must not grant access to application routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.hosts import SearchroomTrustedHostMiddleware


@pytest.mark.parametrize(
    "railway,host,method,path,expected",
    [
        (True, "healthcheck.railway.app", "GET", "/api/v1/health/ready", 503),
        (False, "healthcheck.railway.app", "GET", "/api/v1/health/ready", 400),
        (True, "attacker.invalid", "GET", "/api/v1/health/ready", 400),
        (True, "healthcheck.railway.app", "POST", "/api/v1/health/ready", 400),
        (True, "healthcheck.railway.app", "GET", "/api/v1/auth/csrf", 400),
        (True, "healthcheck.railway.app", "GET", "/", 400),
        (True, "portal.radiumsearch.com", "GET", "/api/v1/health/ready", 503),
    ],
)
def test_railway_probe_host_is_scoped(railway, host, method, path, expected):
    from fastapi.responses import JSONResponse

    app = FastAPI()
    app.add_middleware(
        SearchroomTrustedHostMiddleware,
        allowed_hosts=["portal.radiumsearch.com"],
        railway=railway,
    )

    @app.get("/api/v1/health/ready")
    def unready():
        return JSONResponse({"status": "database unavailable"}, status_code=503)

    with TestClient(app) as client:
        response = client.request(method, path, headers={"Host": host})
    assert response.status_code == expected
    if expected == 503:
        assert response.json() == {"status": "database unavailable"}
