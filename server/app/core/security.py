import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def code_hash(code_id, email, code):
    key = get_settings().jwt_secret.get_secret_value().encode()
    return hmac.new(key, f"{code_id}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def create_token(user_id):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=24)},
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def read_token(token):
    return jwt.decode(
        token,
        get_settings().jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )
