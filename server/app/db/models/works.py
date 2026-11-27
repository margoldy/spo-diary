from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, SmallInteger, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, IdMixin


class Type(IdMixin, Base):
    __tablename__ = "types"
    name: Mapped[str] = mapped_column(Text(collation="und-x-icu"), unique=True)


class Genre(IdMixin, Base):
    __tablename__ = "genres"
    name: Mapped[str] = mapped_column(Text(collation="und-x-icu"))


class Tag(IdMixin, Base):
    __tablename__ = "tags"
    name: Mapped[str] = mapped_column(Text(collation="und-x-icu"))


class WorkGroup(IdMixin, Base):
    __tablename__ = "work_groups"


class WorkFields(IdMixin):
    title: Mapped[str] = mapped_column(Text(collation="und-x-icu"))
    type_id: Mapped[UUID] = mapped_column(ForeignKey("types.id", ondelete="RESTRICT"))
    description: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(SmallInteger)
    cover: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    age_rating: Mapped[str | None] = mapped_column(Text)


class Work(WorkFields, Base):
    __tablename__ = "works"
    __table_args__ = (
        CheckConstraint("year BETWEEN 1 AND 9999", name="year"),
        CheckConstraint(
            "age_rating IN ('0+','6+','12+','16+','18+','G','PG','PG-13','R','R+','R18+')", name="age_rating"
        ),
    )
    group_id: Mapped[UUID | None] = mapped_column(ForeignKey("work_groups.id", ondelete="SET NULL"), index=True)
    genres: Mapped[list[Genre]] = relationship(secondary="work_genres", lazy="selectin", viewonly=True)
    tags: Mapped[list[Tag]] = relationship(secondary="work_tags", lazy="selectin", viewonly=True)


class PrivateWork(WorkFields, Base):
    __tablename__ = "private_works"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("year BETWEEN 1 AND 9999", name="year"),
        CheckConstraint("age_rating IN ('0+','6+','12+','16+','18+')", name="age_rating"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    genres: Mapped[list[Genre]] = relationship(secondary="private_genres", lazy="selectin", viewonly=True)


class WorkGenre(Base):
    __tablename__ = "work_genres"
    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    genre_id: Mapped[UUID] = mapped_column(ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True)


class PrivateGenre(Base):
    __tablename__ = "private_genres"
    private_id: Mapped[UUID] = mapped_column(ForeignKey("private_works.id", ondelete="CASCADE"), primary_key=True)
    genre_id: Mapped[UUID] = mapped_column(ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True)


class WorkTag(Base):
    __tablename__ = "work_tags"
    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


for model in (Genre, Tag):
    Index(f"uq_{model.__tablename__}_name_lower", func.lower(model.name), unique=True)
for model, column in ((Work, "title"), (PrivateWork, "title"), (Tag, "name")):
    Index(
        f"ix_{model.__tablename__}_search",
        func.lower(getattr(model, column)).label("search"),
        postgresql_using="gin",
        postgresql_ops={"search": "gin_trgm_ops"},
    )
Index("ix_work_genres_genre_work", WorkGenre.genre_id, WorkGenre.work_id)
Index("ix_private_genres_genre_private", PrivateGenre.genre_id, PrivateGenre.private_id)
Index("ix_work_tags_tag_work", WorkTag.tag_id, WorkTag.work_id)
