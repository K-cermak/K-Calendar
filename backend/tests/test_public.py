from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import Database
from app.version import VERSION


def test_health_reports_ok_and_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": VERSION}


def test_database_uses_the_required_pragmas(app: FastAPI, client: TestClient) -> None:
    db: Database = app.state.db
    with db.reader() as session:
        connection = session.connection()

        def pragma(name: str) -> object:
            return connection.exec_driver_sql(f"PRAGMA {name}").scalar()

        assert pragma("journal_mode") == "wal"
        assert pragma("foreign_keys") == 1
        assert pragma("busy_timeout") == 5000
        assert pragma("synchronous") == 1  # NORMAL


def test_openapi_schema_is_served(client: TestClient) -> None:
    schema = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/health" in schema["paths"]
