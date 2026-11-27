from typing import Annotated, Literal
from uuid import UUID

from pydantic import BeforeValidator, Field, field_validator, model_validator

from app.schemas.common import AgeRating, Page, Reference, Schema, WorkType, Year, trim_nullable, unique
from app.schemas.library import EntryResponse, FeedbackCreate, LibraryBrief


class PrivateCreate(Schema):
    title: str = Field(min_length=1, max_length=300)
    type: WorkType
    description: Annotated[Annotated[str, Field(max_length=10000)] | None, BeforeValidator(trim_nullable)] = None
    author: Annotated[Annotated[str, Field(max_length=1000)] | None, BeforeValidator(trim_nullable)] = None
    year: Year | None = None
    country: Annotated[Annotated[str, Field(max_length=100)] | None, BeforeValidator(trim_nullable)] = None
    age_rating: AgeRating | None = None
    genre_ids: list[UUID] = Field(default_factory=list, max_length=26)
    entry: FeedbackCreate = Field(default_factory=FeedbackCreate)
    _unique = field_validator("genre_ids")(unique)


class PrivateUpdate(Schema):
    title: str = Field(default=None, min_length=1, max_length=300)
    type: WorkType = None
    description: Annotated[Annotated[str, Field(max_length=10000)] | None, BeforeValidator(trim_nullable)] = None
    author: Annotated[Annotated[str, Field(max_length=1000)] | None, BeforeValidator(trim_nullable)] = None
    year: Year | None = None
    country: Annotated[Annotated[str, Field(max_length=100)] | None, BeforeValidator(trim_nullable)] = None
    age_rating: AgeRating | None = None
    genre_ids: list[UUID] = Field(default_factory=list, max_length=26)
    _unique = field_validator("genre_ids")(unique)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("Передайте хотя бы одно поле")
        return self


class WorkCard(Schema):
    id: UUID
    scope: Literal["catalog", "private"]
    title: str
    type: WorkType
    author: str | None
    year: int | None
    country: str | None
    age_rating: str | None
    cover_url: str | None
    genres: list[Reference]


class CatalogCard(WorkCard):
    library: LibraryBrief | None


class WorkDetail(WorkCard):
    description: str | None
    tags: list[Reference]


class Adaptation(Schema):
    id: UUID
    title: str
    type: WorkType
    cover_url: str | None


class PrivateResponse(Schema):
    work: WorkDetail
    entry: EntryResponse


class WorkResponse(Schema):
    work: WorkDetail
    entry: EntryResponse | None
    adaptations: list[Adaptation]


class LibraryResponse(EntryResponse):
    work: WorkCard


class CoverResponse(Schema):
    cover_url: str


class SourceWork(Schema):
    id: UUID
    scope: Literal["catalog", "private"]
    title: str


class Reason(Schema):
    text: str


class RecommendationReason(Reason):
    source_work: SourceWork | None


class SimilarItem(Schema):
    work: WorkCard
    reason: Reason


class RecommendationItem(Schema):
    work: WorkCard
    reason: RecommendationReason


class SimilarResponse(Page[SimilarItem]):
    basis: Literal["tags", "genres", "none"]


class RecommendationsResponse(Page[RecommendationItem]):
    mode: Literal["personal", "general"]
