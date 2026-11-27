from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import SimilarQuery
from app.schemas.works import (
    CoverResponse,
    LibraryResponse,
    PrivateCreate,
    PrivateResponse,
    PrivateUpdate,
    SimilarResponse,
)
from app.services.covers import MAX_BYTES, CoversService
from app.services.recommendations import RecommendationsService
from app.services.works import WorksService

router = APIRouter(prefix="/me/private-works", tags=["Личные произведения"])


@router.post("", response_model=LibraryResponse, status_code=201)
def create(body: PrivateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WorksService(db).create_private(user.id, body)


@router.get("/{id}", response_model=PrivateResponse)
def get(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WorksService(db).get_private(user.id, id)


@router.patch("/{id}", response_model=PrivateResponse)
def update(id: UUID, body: PrivateUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WorksService(db).update_private(user.id, id, body.model_dump(exclude_unset=True))


@router.put("/{id}/cover", response_model=CoverResponse)
def upload_cover(
    id: UUID, file: Annotated[UploadFile, File()], user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return CoversService(db).replace(user.id, id, file.file.read(MAX_BYTES + 1))


@router.get("/{id}/cover", response_class=Response)
def get_cover(id: UUID, v: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response(
        CoversService(db).get(user.id, id, private=True),
        media_type="image/webp",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/{id}/cover", status_code=204)
def delete_cover(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    CoversService(db).replace(user.id, id)
    return Response(status_code=204)


@router.get("/{id}/similar", response_model=SimilarResponse)
def similar(
    id: UUID,
    filters: Annotated[SimilarQuery, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RecommendationsService(db).similar(user.id, id, filters, private=True)
