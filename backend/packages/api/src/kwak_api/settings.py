from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KWAK_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://kwak:kwak@localhost:5432/kwak"
