from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.reference import TYPE_IDS
from app.db.models import Genre, Hidden, Library, PrivateGenre, PrivateWork, Tag, Work, WorkGenre, WorkTag


def contains(column, text):
    return func.lower(column).contains(text.lower(), autoescape=True)


class WorksQueries:
    def __init__(self, db: Session):
        self.db = db

    def references(self, model, ids):
        if ids and set(self.db.scalars(select(model.id).where(model.id.in_(ids)))) != set(ids):
            raise ApiError(422, "REFERENCE_NOT_FOUND", "Неизвестный жанр или тег")

    def validate_filters(self, filters):
        self.references(Genre, getattr(filters, "genre_ids", []))
        included = getattr(filters, "tag_ids", [])
        excluded = getattr(filters, "exclude_tag_ids", [])
        self.references(Tag, included + excluded)
        if set(included) & set(excluded):
            raise ApiError(422, "FILTER_CONFLICT", "Тег одновременно включён и исключён")

    def get_work(self, work_id: UUID):
        work = self.db.get(Work, work_id)
        if work is None:
            raise ApiError(404, "WORK_NOT_FOUND", "Произведение не найдено")
        return work

    def get_private(self, work_id: UUID, user_id: UUID):
        work = self.db.scalar(select(PrivateWork).where(PrivateWork.id == work_id, PrivateWork.user_id == user_id))
        if work is None:
            raise ApiError(404, "PRIVATE_WORK_NOT_FOUND", "Личное произведение не найдено")
        return work

    def filtered(self, filters):
        self.validate_filters(filters)
        query = select(Work)
        if filters.q:
            query = query.where(contains(Work.title, filters.q))
        if filters.types:
            query = query.where(Work.type_id.in_([TYPE_IDS[t] for t in filters.types]))
        if filters.genre_ids:
            query = query.where(exists().where(WorkGenre.work_id == Work.id, WorkGenre.genre_id.in_(filters.genre_ids)))
        for tag_id in set(getattr(filters, "tag_ids", [])):
            query = query.where(exists().where(WorkTag.work_id == Work.id, WorkTag.tag_id == tag_id))
        if excluded := getattr(filters, "exclude_tag_ids", []):
            query = query.where(~exists().where(WorkTag.work_id == Work.id, WorkTag.tag_id.in_(excluded)))
        return query

    @staticmethod
    def available(query, user_id):
        return query.where(
            ~exists().where(Library.user_id == user_id, Library.work_id == Work.id),
            ~exists().where(Hidden.user_id == user_id, Hidden.work_id == Work.id),
        )

    @staticmethod
    def ordered(query, sort):
        if sort == "year_desc":
            query = query.order_by(Work.year.desc().nulls_last())
        return query.order_by(func.lower(Work.title), Work.id)

    def page(self, query, filters):
        total = self.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        if filters.offset >= total:
            return [], total
        return list(self.db.scalars(query.limit(filters.limit).offset(filters.offset))), total

    def entries(self, user_id, work_ids):
        return {
            row.work_id: row
            for row in self.db.scalars(select(Library).where(Library.user_id == user_id, Library.work_id.in_(work_ids)))
        }

    def adaptations(self, work):
        if work.group_id is None:
            return []
        return list(
            self.db.scalars(
                select(Work)
                .where(Work.group_id == work.group_id, Work.id != work.id)
                .order_by(func.lower(Work.title), Work.id)
            )
        )

    def replace_genres(self, work, genre_ids):
        from sqlalchemy import delete

        self.references(Genre, genre_ids)
        self.db.execute(delete(PrivateGenre).where(PrivateGenre.private_id == work.id))
        self.db.add_all([PrivateGenre(private_id=work.id, genre_id=value) for value in genre_ids])
        self.db.flush()
        self.db.expire(work, ["genres"])
