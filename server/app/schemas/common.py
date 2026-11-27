from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, field_validator

WorkType = Literal[
    "anime",
    "movie",
    "series",
    "animated_movie",
    "animated_series",
    "book",
    "light_novel",
    "web_novel",
    "manga",
    "manhwa",
    "manhua",
    "comic",
    "visual_novel",
    "other",
]
Status = Literal["planned", "in_progress", "completed", "dropped"]
AgeRating = Literal["0+", "6+", "12+", "16+", "18+"]
Rating = Annotated[StrictInt, Field(ge=1, le=5)]
Year = Annotated[StrictInt, Field(ge=1, le=9999)]


def trim_nullable(value):
    return (value.strip() or None) if isinstance(value, str) else value


ReviewText = Annotated[Annotated[str, Field(max_length=5000)] | None, BeforeValidator(trim_nullable)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def supported_text(cls, value):
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("Текст содержит недопустимый нулевой символ")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise ValueError("Некорректный Unicode в тексте") from None
        return value


class TagChoice(Schema):
    tag_id: UUID
    value: Annotated[StrictInt, Field(ge=-1, le=1)]

    @field_validator("value")
    @classmethod
    def nonzero(cls, value):
        if value == 0:
            raise ValueError("Допустимы 1 и -1")
        return value


def unique(values):
    keys = [getattr(item, "tag_id", item) for item in values]
    if len(keys) != len(set(keys)):
        raise ValueError("Повторяющиеся ID недопустимы")
    return values


Choices = Annotated[list[TagChoice], Field(max_length=100)]


class PageQuery(Schema):
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SearchQuery(PageQuery):
    q: str = Field("", max_length=200)


class SimilarQuery(SearchQuery):
    types: list[WorkType] = Field(default_factory=list, max_length=14)
    genre_ids: list[UUID] = Field(default_factory=list, max_length=26)


class CatalogQuery(SimilarQuery):
    tag_ids: list[UUID] = Field(default_factory=list, max_length=30)
    exclude_tag_ids: list[UUID] = Field(default_factory=list, max_length=30)
    sort: Literal["title_asc", "year_desc"] = "title_asc"


class RecommendationsQuery(CatalogQuery):
    sort: Literal["relevance", "title_asc", "year_desc"] = "relevance"


class LibraryQuery(SimilarQuery):
    statuses: list[Status] = Field(default_factory=list, max_length=4)
    scope: Literal["catalog", "private"] | None = None
    sort: Literal["added_desc", "title_asc", "rating_desc"] = "added_desc"


class GenreQuery(Schema):
    q: str = Field("", max_length=200)


T = TypeVar("T")


class Items(Schema, Generic[T]):
    items: list[T]


class Page(Items[T], Generic[T]):
    total: int


class Reference(Schema):
    id: UUID
    name: str


class TypeResponse(Schema):
    code: WorkType
    name: str
