from functools import lru_cache

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine():
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC"},
    )


def get_db(request: Request):
    with Session(get_engine(), expire_on_commit=False) as db:
        if request.method == "GET":
            db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        try:
            yield db
        finally:
            db.rollback()
