from importlib.metadata import version

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from kwak_api.audit.routes import router as audit_router
from kwak_api.auth.routes import router as auth_router
from kwak_api.db import make_engine
from kwak_api.demo.routes import router as demo_router
from kwak_api.forecast.routes import router as forecast_router
from kwak_api.goals.analysis import router as goal_analysis_router
from kwak_api.goals.routes import router as goals_router
from kwak_api.household.routes import router as household_router
from kwak_api.projection.routes import router as projection_router
from kwak_api.retirement.routes import router as retirement_router
from kwak_api.settings import Settings
from kwak_api.spending.budget import router as spending_budget_router
from kwak_api.spending.report import router as spending_report_router
from kwak_api.spending.routes import router as spending_router
from kwak_api.wealth.routes import router as wealth_router


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
    # The Dash pages open their own sessions; tests replace both.
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(household_router)
    app.include_router(demo_router)
    app.include_router(audit_router)
    app.include_router(wealth_router)
    app.include_router(goal_analysis_router)  # before /api/goals/{goal_id}
    app.include_router(goals_router)
    app.include_router(projection_router)
    app.include_router(retirement_router)
    app.include_router(spending_router)
    app.include_router(spending_budget_router)
    app.include_router(spending_report_router)
    app.include_router(forecast_router)
    return app


app = create_app()
