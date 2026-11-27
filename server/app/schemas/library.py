from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import Choices, Rating, Reference, ReviewText, Schema, Status, unique


class FeedbackCreate(Schema):
    status: Status = "planned"
    rating: Rating | None = None
    liked: ReviewText = None
    disliked: ReviewText = None
    comment: ReviewText = None
    manual_tags: Choices = Field(default_factory=list)
    _unique = field_validator("manual_tags")(unique)


class LibraryCreate(FeedbackCreate):
    work_id: UUID


class LibraryUpdate(FeedbackCreate):
    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("Передайте хотя бы одно поле")
        return self


class Analysis(Schema):
    status: Literal["none", "pending", "running", "done", "error"]
    version: int


class Signal(Schema):
    tag: Reference
    value: float
    quote: str | None


class AnalysisResponse(Schema):
    analysis: Analysis
    effective_source: Literal["none", "manual", "review", "rating"]
    signals: list[Signal]


class EntryResponse(AnalysisResponse):
    id: UUID
    status: Status
    rating: int | None
    liked: str | None
    disliked: str | None
    comment: str | None
    created_at: datetime


class LibraryBrief(Schema):
    id: UUID
    status: Status
    rating: int | None
