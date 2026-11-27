from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, IdMixin
from app.db.models.works import PrivateWork, Tag, Work


class Library(IdMixin, Base):
    __tablename__ = "library"
    __table_args__ = (
        UniqueConstraint("user_id", "work_id"),
        UniqueConstraint("private_id"),
        ForeignKeyConstraint(
            ["user_id", "private_id"],
            ["private_works.user_id", "private_works.id"],
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("(work_id IS NOT NULL) <> (private_id IS NOT NULL)", name="one_work"),
        CheckConstraint("status IN ('planned','in_progress','completed','dropped')", name="status"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),
        CheckConstraint("version >= 0", name="version"),
        CheckConstraint("analysis IN ('pending','running','done','error')", name="analysis"),
        CheckConstraint(
            "(liked IS NULL AND disliked IS NULL AND comment IS NULL) = (analysis IS NULL)", name="review_state"
        ),
        CheckConstraint(
            "(liked IS NULL OR btrim(liked) <> '') AND (disliked IS NULL OR btrim(disliked) <> '') AND (comment IS NULL OR btrim(comment) <> '')",
            name="review_nonempty",
        ),
        CheckConstraint(
            "coalesce(length(liked),0)+coalesce(length(disliked),0)+coalesce(length(comment),0)<=5000",
            name="review_length",
        ),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    work_id: Mapped[UUID | None] = mapped_column(ForeignKey("works.id", ondelete="RESTRICT"), index=True)
    private_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(Text, default="planned", server_default="planned")
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    liked: Mapped[str | None] = mapped_column(Text)
    disliked: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    analysis: Mapped[str | None] = mapped_column(Text, index=True)
    version: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    work: Mapped[Work | None] = relationship(lazy="selectin")
    private_work: Mapped[PrivateWork | None] = relationship(lazy="selectin", viewonly=True)
    signals: Mapped[list["LibraryTag"]] = relationship(lazy="selectin", viewonly=True)


class LibraryTag(Base):
    __tablename__ = "library_tags"
    __table_args__ = (
        CheckConstraint(
            "(source='review' AND value IN (-1,0,1) AND quote IS NOT NULL AND btrim(quote)<>'') OR "
            "(source='manual' AND value IN (-1,1) AND quote IS NULL) OR "
            "(source='rating' AND value IN (-0.3,-0.2,0.2,0.3) AND quote IS NULL)",
            name="signal",
        ),
    )
    library_id: Mapped[UUID] = mapped_column(ForeignKey("library.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(Text)
    quote: Mapped[str | None] = mapped_column(Text)
    tag: Mapped[Tag] = relationship(lazy="selectin")


class UserTag(Base):
    __tablename__ = "user_tags"
    __table_args__ = (
        CheckConstraint("positive>=0 AND negative>=0", name="sums"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True)
    positive: Mapped[Decimal] = mapped_column(Numeric, default=0, server_default="0")
    negative: Mapped[Decimal] = mapped_column(Numeric, default=0, server_default="0")
    weight: Mapped[Decimal] = mapped_column(
        Numeric,
        Computed(
            "(positive-negative)/(2+positive+negative)",
            persisted=True,
        ),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[Decimal] = mapped_column(Numeric)


class Hidden(Base):
    __tablename__ = "hidden"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)


Index("ix_library_tags_tag_library", LibraryTag.tag_id, LibraryTag.library_id)
Index("ix_user_tags_tag_user", UserTag.tag_id, UserTag.user_id)
Index("ix_recommendations_order", Recommendation.user_id, Recommendation.score.desc(), Recommendation.work_id)
