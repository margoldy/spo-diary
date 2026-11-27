from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

APP_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=APP_DIR / ".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_user: str = "postgres"
    db_password: SecretStr = SecretStr("")
    db_name: str = Field(default="spo_diary_db", min_length=1)
    jwt_secret: SecretStr = Field(min_length=32)
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:8000"]
    cookie_secure: bool = True
    storage_dir: Path = APP_DIR / "covers"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_tls: bool = True
    smtp_ssl: bool = False
    yandex_api_key: SecretStr = SecretStr("")
    yandex_model_uri: str = ""
    model_timeout: float = 60

    @property
    def database_url(self):
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
