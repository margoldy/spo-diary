from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User
from app.db.queries.library import LibraryQueries
from app.db.session import get_db
from app.schemas.common import LibraryQuery, Page
from app.schemas.library import AnalysisResponse, LibraryCreate, LibraryUpdate
from app.schemas.works import LibraryResponse
from app.services.library import LibraryService
from app.services.presenters import analysis_response

router = APIRouter(prefix="/me/library", tags=["Библиотека"])


@router.get("", response_model=Page[LibraryResponse])
def entries(
    filters: Annotated[LibraryQuery, Query()], user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return LibraryService(db).list(user.id, filters)


@router.post("", response_model=LibraryResponse, status_code=201)
def add(body: LibraryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LibraryService(db).create(user.id, body)


@router.get("/{id}", response_model=LibraryResponse)
def entry(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LibraryService(db).get(user.id, id)


@router.patch("/{id}", response_model=LibraryResponse)
def update(id: UUID, body: LibraryUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LibraryService(db).update(user.id, id, body.model_dump(exclude_unset=True))


@router.delete("/{id}", status_code=204)
def delete(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    LibraryService(db).delete(user.id, id)
    return Response(status_code=204)


@router.get("/{id}/analysis", response_model=AnalysisResponse)
def analysis(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_response(LibraryQueries(db).get_entry(id, user.id))


@router.post("/{id}/analysis/retry", response_model=AnalysisResponse, status_code=202)
def retry(id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LibraryService(db).retry(user.id, id)
