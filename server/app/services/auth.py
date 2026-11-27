import hmac
import math
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.limits import limiter
from app.core.mail import send_code
from app.core.security import code_hash
from app.db.models import Code, User
from app.db.queries.auth import AuthQueries


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.queries = AuthQueries(db)

    def request_code(self, email: str, ip: str):
        limiter.check((("send-ip", ip), 20, 3600))
        self.queries.lock_email(email)
        previous = self.queries.by_email(email)
        now = datetime.now(timezone.utc)
        if previous is not None and (now - previous.created_at).total_seconds() < 60:
            delay = math.ceil(60 - (now - previous.created_at).total_seconds())
            raise ApiError(429, "RATE_LIMITED", "Подождите перед повторной отправкой", details={"retry_after": delay})
        limiter.check((("send-email", email), 5, 3600))
        code_id, code = uuid4(), f"{secrets.randbelow(1000000):06d}"
        expires = now + timedelta(minutes=10)
        send_code(email, code)
        if previous is not None:
            self.db.delete(previous)
            self.db.flush()
        self.db.add(
            Code(
                id=code_id,
                email=email,
                hash=code_hash(code_id, email, code),
                created_at=now,
                expires_at=expires,
                attempts=0,
            )
        )
        self.db.commit()
        return {"code_id": code_id, "expires_at": expires, "resend_after": 60}

    def verify_code(self, code_id, value, ip):
        limiter.check((("verify-ip", ip), 30, 600))
        row = self.queries.by_id(code_id)
        if row is None:
            raise ApiError(422, "CODE_INVALID", "Неверный код", details={"attempts_left": None})
        if row.expires_at <= datetime.now(timezone.utc):
            raise ApiError(410, "CODE_EXPIRED", "Срок кода истёк")
        if row.attempts >= 5:
            raise ApiError(429, "CODE_ATTEMPTS_EXCEEDED", "Запросите новый код")
        if not hmac.compare_digest(row.hash, code_hash(row.id, row.email, value)):
            row.attempts += 1
            attempts_left = 5 - row.attempts
            self.db.commit()
            raise ApiError(422, "CODE_INVALID", "Неверный код", details={"attempts_left": attempts_left})
        user = self.queries.user(row.email)
        is_new = user is None
        if user is None:
            user = User(email=row.email, name="Пользователь", role="user")
            self.db.add(user)
        self.db.delete(row)
        self.db.commit()
        return user, is_new
