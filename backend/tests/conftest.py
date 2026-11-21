from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(base_url="http://testserver", data_dir=tmp_path / "data")


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>index</title>")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)")
    (dist / "sw.js").write_text("self")
    return dist


@pytest.fixture
def app(settings: Settings, static_dir: Path) -> FastAPI:
    return create_app(settings, static_dir=static_dir)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def new_client(app: FastAPI, client: TestClient) -> Callable[[], TestClient]:
    """Another browser: same server, its own cookie jar. Depends on client so the app has started."""
    return lambda: TestClient(app)
