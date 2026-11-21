from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.helpers import create_event


def test_tags_are_created_on_first_use_with_distinct_colours(admin: TestClient) -> None:
    event = create_event(admin, tags=["travel", "kids", "Travel ", "deadline"])
    assert [t["name"] for t in event["tags"]] == ["deadline", "kids", "travel"]
    colours = [t["color"] for t in admin.get("/api/v1/tags").json()]
    assert len(set(colours)) == 3
    again = create_event(admin, tags=["TRAVEL"])
    assert again["tags"][0]["id"] == next(t["id"] for t in event["tags"] if t["name"] == "travel")


def test_names_compare_case_insensitively_beyond_ascii(admin: TestClient) -> None:
    first = admin.post("/api/v1/tags", json={"name": "Zubař"})
    assert first.status_code == 201
    duplicate = admin.post("/api/v1/tags", json={"name": "ZUBAŘ"})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "tag_exists"
    event = create_event(admin, tags=["zubař"])
    assert event["tags"][0]["id"] == first.json()["id"]


def test_least_used_colour_skips_taken_ones(admin: TestClient) -> None:
    admin.post("/api/v1/tags", json={"name": "a", "color": "red"})
    auto = admin.post("/api/v1/tags", json={"name": "b"}).json()
    assert auto["color"] == "orange"


def test_rename_recolour_and_conflicts(admin: TestClient) -> None:
    kids = admin.post("/api/v1/tags", json={"name": "kids"}).json()
    admin.post("/api/v1/tags", json={"name": "travel"})
    renamed = admin.patch(f"/api/v1/tags/{kids['id']}", json={"name": "Children", "color": "pink"})
    assert renamed.json() == {"id": kids["id"], "name": "Children", "color": "pink"}
    clash = admin.patch(f"/api/v1/tags/{kids['id']}", json={"name": "TRAVEL"})
    assert clash.json()["code"] == "tag_exists"
    same = admin.patch(f"/api/v1/tags/{kids['id']}", json={"name": "children"})
    assert same.json()["name"] == "children"


def test_deleting_a_tag_keeps_its_events(admin: TestClient) -> None:
    event = create_event(admin, tags=["kids"])
    tag_id = event["tags"][0]["id"]
    assert admin.delete(f"/api/v1/tags/{tag_id}").status_code == 204
    after = admin.get(f"/api/v1/events/{event['id']}").json()
    assert after["tags"] == []
    assert after["title"] == "Meeting"


def test_tags_stay_without_events(admin: TestClient) -> None:
    event = create_event(admin, tags=["kids"])
    admin.delete(f"/api/v1/events/{event['id']}")
    assert [t["name"] for t in admin.get("/api/v1/tags").json()] == ["kids"]


def test_tag_input_is_validated(admin: TestClient) -> None:
    assert admin.post("/api/v1/tags", json={"name": "   "}).json()["code"] == "name_required"
    assert admin.post("/api/v1/tags", json={"name": "x", "color": "beige"}).status_code == 422


def test_other_users_tags_are_not_found(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    other = make_user()
    theirs = other.post("/api/v1/tags", json={"name": "secret"}).json()["id"]
    assert admin.get("/api/v1/tags").json() == []
    assert admin.patch(f"/api/v1/tags/{theirs}", json={"name": "x"}).status_code == 404
    assert admin.delete(f"/api/v1/tags/{theirs}").status_code == 404
    # The same name is a separate tag per user.
    mine = admin.post("/api/v1/tags", json={"name": "secret"})
    assert mine.status_code == 201
    assert mine.json()["id"] != theirs


def test_tag_endpoints_need_a_session(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/v1/tags"),
        ("POST", "/api/v1/tags"),
        ("PATCH", "/api/v1/tags/1"),
        ("DELETE", "/api/v1/tags/1"),
    ]:
        assert client.request(method, path, json={}).status_code == 401, (method, path)
