from importlib.metadata import version

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from kwak_api.accounts.routes import router as accounts_router
from kwak_api.auth.routes import router as auth_router
from kwak_api.categories.routes import router as categories_router
from kwak_api.db import make_engine
from kwak_api.household.routes import router as household_router
from kwak_api.imports.routes import router as imports_router
from kwak_api.rules.routes import router as rules_router
from kwak_api.settings import Settings
from kwak_api.transactions.routes import router as transactions_router


class Health(BaseModel):
    status: str
    version: str


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> Health:
    return Health(status="ok", version=version("kwak-api"))


def _operation_id(route: APIRoute) -> str:
    """`totp_verify` -> `totpVerify`: the function name in the generated TypeScript SDK."""
    head, *rest = route.name.split("_")
    return head + "".join(word.capitalize() for word in rest)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Kwak Finance API",
        version=version("kwak-api"),
        generate_unique_id_function=_operation_id,
    )
    app.state.settings = settings
    # The engine connects lazily, on the first request that needs the database.
    app.state.sessionmaker = sessionmaker(make_engine(settings.database_url))
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(household_router)
    app.include_router(accounts_router)
    app.include_router(imports_router)
    app.include_router(transactions_router)
    app.include_router(categories_router)
    app.include_router(rules_router)
    return app


app = create_app()
