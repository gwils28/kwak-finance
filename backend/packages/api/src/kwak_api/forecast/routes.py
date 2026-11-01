"""The cash-flow forecast (spec §4.14 F-FCT-6): the household's next twelve months, computed when
the page asks (nothing saved; the last few results kept in memory by the service)."""

from fastapi import APIRouter
from kwak_core.forecast import MIN_HISTORY

from kwak_api.auth.routes import CurrentSession, Db, Now
from kwak_api.forecast.view import ForecastPageOut, forecast_out
from kwak_api.services import forecast as service

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("")
def get_forecast(user_session: CurrentSession, db: Db, now: Now) -> ForecastPageOut:
    """For the household: spending is the household's (spec §3)."""
    today = now.date()
    try:
        r = service.compute(db, user_session.user.household_id, today)
    except service.NotEnoughHistoryError as short:
        return ForecastPageOut(complete_months=short.months, needed=MIN_HISTORY, forecast=None)
    return ForecastPageOut(
        complete_months=len(r.history), needed=MIN_HISTORY, forecast=forecast_out(r, today)
    )
