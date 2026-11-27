from uuid import UUID

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import read_token
from app.db.models import User
from app.db.session import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    try:
        claims = read_token(request.cookies.get("access_token", ""))
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise ApiError(401, "UNAUTHORIZED", "Нужен вход")
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Нужен вход")
    return user
