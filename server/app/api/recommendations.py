from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Page, PageQuery, RecommendationsQuery
from app.schemas.works import CatalogCard, RecommendationsResponse
from app.services.recommendations import RecommendationsService

router = APIRouter(prefix="/me", tags=["Рекомендации"])


@router.get("/recommendations", response_model=RecommendationsResponse)
def recommendations(
    filters: Annotated[RecommendationsQuery, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RecommendationsService(db).list(user.id, filters)


@router.get("/hidden", response_model=Page[CatalogCard])
def hidden(
    filters: Annotated[PageQuery, Query()], user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return RecommendationsService(db).hidden(user.id, filters)


@router.put("/hidden/{work_id}", status_code=204)
def hide(work_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    RecommendationsService(db).hide(user.id, work_id, True)
    return Response(status_code=204)


@router.delete("/hidden/{work_id}", status_code=204)
def restore(work_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    RecommendationsService(db).hide(user.id, work_id, False)
    return Response(status_code=204)
