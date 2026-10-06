import base64
import binascii
import hashlib
from datetime import timedelta
from typing import Self

from kwak_core.sessions import SessionPolicy
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Only used when KWAK_ENV=dev and no key is set. Never protects real data.
_DEV_KEY = hashlib.sha256(b"kwak-finance insecure dev key").digest()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KWAK_", env_file=".env", extra="ignore")

    # Defaults to prod: forgetting KWAK_ENV must never enable the insecure dev key.
    env: str = "prod"
    database_url: str = "postgresql+psycopg://kwak:kwak@localhost:5432/kwak"
    session_idle_days: int = 7
    session_absolute_days: int = 30
    # Browsers accept Secure cookies on http://localhost, so this stays on in dev.
    cookie_secure: bool = True
    # 32 random bytes, base64url: `kwak generate-key`. Encrypts TOTP secrets at rest.
    secret_key: SecretStr | None = None

    @model_validator(mode="after")
    def _check_secret_key(self) -> Self:
        if self.secret_key is None:
            if self.env != "dev":
                raise ValueError("KWAK_SECRET_KEY is required when KWAK_ENV is not 'dev'")
        else:
            self._decode_key(self.secret_key)
        return self

    @staticmethod
    def _decode_key(value: SecretStr) -> bytes:
        try:
            key = base64.urlsafe_b64decode(value.get_secret_value())
        except (binascii.Error, ValueError):
            key = b""
        if len(key) != 32:
            raise ValueError("KWAK_SECRET_KEY must be base64url for exactly 32 bytes")
        return key

    @property
    def encryption_key(self) -> bytes:
        return _DEV_KEY if self.secret_key is None else self._decode_key(self.secret_key)

    @property
    def session_policy(self) -> SessionPolicy:
        return SessionPolicy(
            idle=timedelta(days=self.session_idle_days),
            absolute=timedelta(days=self.session_absolute_days),
        )
