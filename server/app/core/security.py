import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

ACCESS_TTL = 15 * 60
REFRESH_TTL = 30 * 24 * 60 * 60


def code_hash(code_id, email, code):
    key = get_settings().jwt_secret.get_secret_value().encode()
    return hmac.new(key, f"{code_id}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def create_token(user_id, token_type="access"):
    ttl = {"access": ACCESS_TTL, "refresh": REFRESH_TTL}[token_type]
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "type": token_type, "iat": now, "exp": now + timedelta(seconds=ttl)},
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def read_token(token, token_type="access"):
    claims = jwt.decode(
        token,
        get_settings().jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "type", "iat", "exp"]},
    )
    if claims["type"] != token_type:
        raise jwt.InvalidTokenError("Неверный тип токена")
    return claims
