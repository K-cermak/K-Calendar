from fastapi import APIRouter, Response

from app.db import DbSession
from app.schemas.public import HealthResponse
from app.services import instance
from app.version import VERSION

router = APIRouter(tags=["public"])


@router.get("/health")
def health(session: DbSession) -> HealthResponse:
    instance.check_database(session)
    return HealthResponse(status="ok", version=VERSION)


# Uptime monitors often probe with HEAD; kept out of the schema so the client types stay as they are.
@router.head("/health", include_in_schema=False)
def health_head(session: DbSession) -> Response:
    instance.check_database(session)
    return Response()
