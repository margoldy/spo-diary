from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.reference import TYPE_IDS
from app.db.models import Genre, PrivateWork, Tag
from app.db.queries.library import LibraryQueries
from app.db.queries.works import WorksQueries, contains
from app.services.library import LibraryService
from app.services.presenters import catalog_card, cover_url, entry_response, reference, work_detail


class WorksService:
    def __init__(self, db: Session):
        self.db = db
        self.queries = WorksQueries(db)
        self.library = LibraryQueries(db)

    def list(self, user_id, filters):
        rows, total = self.queries.page(self.queries.ordered(self.queries.filtered(filters), filters.sort), filters)
        entries = self.queries.entries(user_id, [row.id for row in rows])
        return {"items": [catalog_card(row, entries.get(row.id)) for row in rows], "total": total}

    def get(self, user_id, work_id):
        work = self.queries.get_work(work_id)
        entry = self.queries.entries(user_id, [work_id]).get(work_id)
        return {
            "work": work_detail(work),
            "entry": entry_response(entry) if entry else None,
            "adaptations": [
                {"id": row.id, "title": row.title, "type": work_detail(row)["type"], "cover_url": cover_url(row)}
                for row in self.queries.adaptations(work)
            ],
        }

    def get_private(self, user_id, work_id):
        work = self.queries.get_private(work_id, user_id)
        entry = self.library.get_private_entry(work_id, user_id)
        return {"work": work_detail(work), "entry": entry_response(entry)}

    def create_private(self, user_id, body):
        self.library.lock_user(user_id)
        service = LibraryService(self.db)
        before = service.preferences.state(user_id)
        values = body.model_dump(exclude={"entry", "genre_ids", "type"})
        work = PrivateWork(user_id=user_id, type_id=TYPE_IDS[body.type], **values)
        self.db.add(work)
        self.db.flush()
        self.queries.replace_genres(work, body.genre_ids)
        entry = service.create_entry(user_id, body.entry.model_dump(), private_id=work.id)
        service.preferences.rescore_if_changed(user_id, before)
        self.db.commit()
        return entry_response(entry, include_work=True)

    def update_private(self, user_id, work_id, values):
        self.library.lock_user(user_id)
        work = self.queries.get_private(work_id, user_id)
        if "type" in values:
            values["type_id"] = TYPE_IDS[values.pop("type")]
        if "genre_ids" in values:
            self.queries.replace_genres(work, values.pop("genre_ids"))
        for key, value in values.items():
            setattr(work, key, value)
        self.db.commit()
        return self.get_private(user_id, work_id)

    def genres(self, query):
        rows = self.db.scalars(
            select(Genre).where(contains(Genre.name, query)).order_by(func.lower(Genre.name), Genre.id)
        )
        return {"items": [reference(row) for row in rows]}

    def tags(self, filters):
        query = select(Tag).where(contains(Tag.name, filters.q)).order_by(func.lower(Tag.name), Tag.id)
        rows, total = self.queries.page(query, filters)
        return {"items": [reference(row) for row in rows], "total": total}
