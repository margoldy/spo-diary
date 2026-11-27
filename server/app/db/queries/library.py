from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.reference import TYPE_IDS
from app.db.models import Library, PrivateGenre, PrivateWork, User, Work, WorkGenre
from app.db.queries.works import WorksQueries, contains

CATALOG_LOCK = 738421


class LibraryQueries:
    def __init__(self, db: Session):
        self.db = db

    def lock_user(self, user_id):
        self.db.execute(text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": CATALOG_LOCK})
        user = self.db.scalar(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )
        if user is None:
            raise ApiError(401, "UNAUTHORIZED", "Нужен вход")
        return user

    def get_entry(self, entry_id, user_id, *, lock=False):
        query = select(Library).where(Library.id == entry_id, Library.user_id == user_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        entry = self.db.scalar(query)
        if entry is None:
            raise ApiError(404, "LIBRARY_ENTRY_NOT_FOUND", "Запись не найдена")
        return entry

    def get_private_entry(self, private_id, user_id):
        return self.db.scalar(select(Library).where(Library.private_id == private_id, Library.user_id == user_id))

    def filtered(self, user_id, filters):
        WorksQueries(self.db).validate_filters(filters)
        title = func.coalesce(Work.title, PrivateWork.title)
        type_id = func.coalesce(Work.type_id, PrivateWork.type_id)
        query = (
            select(Library)
            .outerjoin(Work, Work.id == Library.work_id)
            .outerjoin(PrivateWork, (PrivateWork.id == Library.private_id) & (PrivateWork.user_id == Library.user_id))
            .where(Library.user_id == user_id)
        )
        if filters.q:
            query = query.where(contains(title, filters.q))
        if filters.types:
            query = query.where(type_id.in_([TYPE_IDS[value] for value in filters.types]))
        if filters.statuses:
            query = query.where(Library.status.in_(filters.statuses))
        if filters.scope:
            query = query.where(
                Library.work_id.is_not(None) if filters.scope == "catalog" else Library.private_id.is_not(None)
            )
        if filters.genre_ids:
            query = query.where(
                or_(
                    exists().where(WorkGenre.work_id == Library.work_id, WorkGenre.genre_id.in_(filters.genre_ids)),
                    exists().where(
                        PrivateGenre.private_id == Library.private_id, PrivateGenre.genre_id.in_(filters.genre_ids)
                    ),
                )
            )
        if filters.sort == "added_desc":
            query = query.order_by(Library.created_at.desc())
        elif filters.sort == "rating_desc":
            query = query.order_by(Library.rating.desc().nulls_last())
        return query.order_by(func.lower(title), Library.id)
