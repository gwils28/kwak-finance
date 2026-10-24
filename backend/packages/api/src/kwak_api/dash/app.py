"""The Dash app, mounted at /dash (ARCHITECTURE: exploratory analytics pages, embedded in the
React app). It answers only a fully signed-in session, as the API: `DashGate` checks the
session cookie and hands the user's id to the pages in a header it sets itself. The pages only
read: nothing is saved from Dash, so its callbacks need no CSRF token (the cookie is SameSite
Lax, and a cross-site POST carries none)."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from uuid import UUID

import flask
from a2wsgi import WSGIMiddleware
from dash import Dash, Input, Output, dcc, html
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import State
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from kwak_api.auth.routes import SESSION_COOKIE
from kwak_api.auth.sessions import find_active_session
from kwak_api.dash import i18n
from kwak_api.models import User

PREFIX = "/dash/"
USER_HEADER = "X-Kwak-User"
"""Set by the gate on every request it lets through, never taken from the client."""
_USER_KEY = USER_HEADER.lower().encode()

INDEX = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap"
    />
    {%css%}
    <style>
      body { margin: 0; font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif; }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
  </body>
</html>"""


class Context:
    """What a page's callbacks need from the API: a database session, the clock and the
    signed-in user."""

    def __init__(self, state: State) -> None:
        self._state = state

    def db(self) -> AbstractContextManager[Session]:
        scope: Callable[[], AbstractContextManager[Session]] = self._state.db_scope
        return scope()

    def now(self) -> datetime:
        clock: Callable[[], datetime] = self._state.clock
        return clock()

    @staticmethod
    def viewer(db: Session) -> User:
        return db.get_one(User, UUID(flask.request.headers[USER_HEADER]))


class DashGate:
    def __init__(self, state: State, app: ASGIApp) -> None:
        self._state = state
        self._app = app

    def _user_id(self, token: str) -> UUID | None:
        context = Context(self._state)
        with context.db() as db:
            session = find_active_session(
                db, token, context.now(), self._state.settings.session_policy
            )
            if session is None or session.mfa_verified_at is None:
                return None
            return session.user_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        token = Request(scope).cookies.get(SESSION_COOKIE)
        user_id = await run_in_threadpool(self._user_id, token) if token else None
        if user_id is None:
            lang = i18n.language(Request(scope).query_params.get("lang"))
            message = i18n.t(lang, "not_signed_in")
            await PlainTextResponse(message, status_code=401)(scope, receive, send)
            return
        headers = [(k, v) for k, v in scope["headers"] if k != _USER_KEY]
        headers.append((_USER_KEY, str(user_id).encode()))
        await self._app({**scope, "headers": headers}, receive, send)


def create_dash(state: State) -> ASGIApp:
    # Imported here: the pages import this module for Context.
    from kwak_api.dash import projection

    app = Dash(
        __name__,
        requests_pathname_prefix=PREFIX,
        routes_pathname_prefix="/",
        title="Kwak Finance",
        update_title="",  # keeps the page title while a callback runs
        suppress_callback_exceptions=True,
        serve_locally=True,
    )
    app.index_string = INDEX
    app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page")])
    context = Context(state)
    pages = {"projection": projection.register(app, context)}

    @app.callback(Output("page", "children"), Input("url", "pathname"), Input("url", "search"))
    def page(pathname: str | None, search: str | None) -> object:
        name = (pathname or "").removeprefix(PREFIX).strip("/")
        render = pages.get(name)
        if render is None:
            return html.P(i18n.t(projection.view_of(search or "").lang, "not_found"))
        return render(search or "")

    return DashGate(state, WSGIMiddleware(app.server))  # type: ignore[arg-type]
