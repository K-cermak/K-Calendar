import logging

from fastapi.testclient import TestClient

from app.security import RedactTokensFilter


def test_cross_origin_writes_to_the_api_are_refused(client: TestClient) -> None:
    response = client.post("/api/v1/health", headers={"origin": "https://evil.test"})
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "cross_origin"
    assert "came from https://evil.test, but APP_BASE_URL is http://testserver" in body["message"]


def test_sec_fetch_site_is_checked_without_origin(client: TestClient) -> None:
    for site in ("cross-site", "same-site"):
        response = client.post("/api/v1/nope", headers={"sec-fetch-site": site})
        assert response.status_code == 403, site
    for site in ("same-origin", "none"):
        response = client.post("/api/v1/nope", headers={"sec-fetch-site": site})
        assert response.status_code == 404, site


def test_bearer_requests_skip_the_origin_check(client: TestClient) -> None:
    response = client.post(
        "/api/v1/nope", headers={"origin": "https://evil.test", "authorization": "Bearer x"}
    )
    assert response.status_code == 404


def test_cross_origin_reads_are_not_blocked(client: TestClient) -> None:
    assert client.get("/api/v1/health", headers={"origin": "https://evil.test"}).status_code == 200


def test_security_headers(client: TestClient) -> None:
    for path in ("/", "/api/v1/health", "/api/v1/nope"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
        csp = headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "img-src 'self' blob: data:" in csp
        assert "connect-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp


def test_api_docs_page_loads(client: TestClient) -> None:
    response = client.get("/api/v1/docs")
    assert response.status_code == 200
    assert "cdn.jsdelivr.net" in response.headers["content-security-policy"]


def test_access_log_redacts_link_tokens() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4", "GET", "/invite/s3cret?x=1", "1.1", 200),
        None,
    )
    RedactTokensFilter().filter(record)
    assert "s3cret" not in record.getMessage()
    assert "/invite/[redacted]?x=1" in record.getMessage()
