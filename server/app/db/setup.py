import psycopg
from psycopg import sql

from app.core.config import get_settings


def create_database():
    url = get_settings().database_url.set(drivername="postgresql")
    try:
        with psycopg.connect(url.render_as_string(hide_password=False), connect_timeout=3):
            return
    except psycopg.OperationalError:
        pass
    try:
        with psycopg.connect(
            url.set(database="postgres").render_as_string(hide_password=False),
            autocommit=True,
            connect_timeout=3,
        ) as connection:
            if connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (url.database,)).fetchone():
                raise SystemExit("База PostgreSQL недоступна по параметрам DB_*.")
            try:
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
            except psycopg.errors.DuplicateDatabase:
                pass
    except psycopg.Error:
        raise SystemExit("Не удалось подключиться к PostgreSQL или создать базу.") from None
