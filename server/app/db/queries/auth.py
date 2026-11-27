from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Code, User


class AuthQueries:
    def __init__(self, db: Session):
        self.db = db

    def lock_email(self, email):
        self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 91))"), {"email": email})

    def by_email(self, email):
        return self.db.scalar(select(Code).where(Code.email == email).with_for_update())

    def by_id(self, code_id):
        return self.db.scalar(select(Code).where(Code.id == code_id).with_for_update())

    def user(self, email):
        return self.db.scalar(select(User).where(User.email == email))
