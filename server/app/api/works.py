from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.reference import TYPES
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import CatalogQuery, GenreQuery, Items, Page, Reference, SearchQuery, SimilarQuery, TypeResponse
from app.schemas.works import CatalogCard, SimilarResponse, WorkResponse
from app.services.covers import CoversService
from app.services.recommendations import RecommendationsService
from app.services.works import WorksService

router = APIRouter(tags=["Каталог"], dependencies=[Depends(get_current_user)])


@router.get("/types", response_model=Items[TypeResponse])
def types():
    return {"items": [{"code": code, "name": name} for code, name in TYPES.items()]}


@router.get("/genres", response_model=Items[Reference])
def genres(filters: Annotated[GenreQuery, Query()], db: Session = Depends(get_db)):
    return WorksService(db).genres(filters.q)


@router.get("/tags", response_model=Page[Reference])
def tags(filters: Annotated[SearchQuery, Query()], db: Session = Depends(get_db)):
    return WorksService(db).tags(filters)


@router.get("/works", response_model=Page[CatalogCard])
def works(
    filters: Annotated[CatalogQuery, Query()], user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return WorksService(db).list(user.id, filters)


@router.get("/works/{id}", response_model=WorkResponse)
def work(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WorksService(db).get(user.id, id)


@router.get("/works/{id}/cover", response_class=Response)
def cover(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response(
        CoversService(db).get(user.id, id), media_type="image/webp", headers={"Cache-Control": "private, no-store"}
    )


@router.get("/works/{id}/similar", response_model=SimilarResponse)
def similar(
    id: UUID,
    filters: Annotated[SimilarQuery, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RecommendationsService(db).similar(user.id, id, filters)
