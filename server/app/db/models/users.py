from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, IdMixin


class User(IdMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="role"),)
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, default="Пользователь")
    role: Mapped[str] = mapped_column(Text, default="user", server_default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Code(IdMixin, Base):
    __tablename__ = "codes"
    __table_args__ = (CheckConstraint("attempts BETWEEN 0 AND 5", name="attempts"),)
    email: Mapped[str] = mapped_column(Text, unique=True)
    hash: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
