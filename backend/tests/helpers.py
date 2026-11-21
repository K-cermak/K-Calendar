from typing import Any

from fastapi.testclient import TestClient


def personal(client: TestClient) -> int:
    return client.get("/api/v1/calendars").json()[0]["id"]


def create_event(client: TestClient, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "calendar_id": fields.pop("calendar_id", None) or personal(client),
        "title": "Meeting",
        "start": "2026-11-23T09:00:00",
        "end": "2026-11-23T10:00:00",
        **fields,
    }
    response = client.post("/api/v1/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def occurrences(client: TestClient, start: str, end: str, tz: str | None = None) -> list[dict[str, Any]]:
    params = {"start": start, "end": end} | ({"tz": tz} if tz else {})
    response = client.get("/api/v1/occurrences", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]
