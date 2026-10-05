from importlib.metadata import version

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel


class Health(BaseModel):
    status: str
    version: str


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> Health:
    return Health(status="ok", version=version("kwak-api"))


def create_app() -> FastAPI:
    app = FastAPI(title="Kwak Finance API", version=version("kwak-api"))
    app.include_router(router)
    return app


app = create_app()
