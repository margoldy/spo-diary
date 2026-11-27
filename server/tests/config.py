import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url


def database_url():
    if address := os.environ.get("TEST_DATABASE_URL"):
        return make_url(address)
    values = dotenv_values(Path(__file__).resolve().parents[1] / "app/.env")
    return URL.create(
        "postgresql+psycopg",
        username=values.get("DB_USER", "postgres"),
        password=values.get("DB_PASSWORD", ""),
        host=values.get("DB_HOST", "localhost"),
        port=int(values.get("DB_PORT", "5432")),
        database=values.get("DB_NAME", "spo_diary_db"),
    )


def database_env(url):
    return {
        "DB_HOST": url.host,
        "DB_PORT": str(url.port or 5432),
        "DB_USER": url.username,
        "DB_PASSWORD": url.password or "",
        "DB_NAME": url.database,
    }
