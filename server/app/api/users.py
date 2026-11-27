from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User
from app.db.queries.library import LibraryQueries
from app.db.session import get_db
from app.schemas.auth import UserResponse, UserUpdate

router = APIRouter(prefix="/me", tags=["Профиль"])


@router.get("", response_model=UserResponse)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("", response_model=UserResponse)
def update_profile(body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = LibraryQueries(db).lock_user(user.id)
    user.name = body.name
    db.commit()
    return user
