from datetime import timedelta

from kwak_core.sessions import SessionPolicy
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KWAK_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://kwak:kwak@localhost:5432/kwak"
    session_idle_days: int = 7
    session_absolute_days: int = 30
    # Browsers accept Secure cookies on http://localhost, so this stays on in dev.
    cookie_secure: bool = True

    @property
    def session_policy(self) -> SessionPolicy:
        return SessionPolicy(
            idle=timedelta(days=self.session_idle_days),
            absolute=timedelta(days=self.session_absolute_days),
        )
