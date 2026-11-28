from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Hidden, Work
from app.db.queries.library import LibraryQueries
from app.db.queries.recommendations import RecommendationsQueries
from app.db.queries.works import WorksQueries
from app.services.presenters import catalog_card, work_card


class RecommendationsService:
    def __init__(self, db: Session):
        self.db = db
        self.queries = RecommendationsQueries(db)
        self.works = WorksQueries(db)
        self.library = LibraryQueries(db)

    def reason(self, user_id, work_id, mode):
        if mode == "general":
            return {"text": "Общая подборка по выбранным фильтрам.", "source_work": None}
        tag, entry, source = self.queries.reason_source(user_id, work_id)
        if entry is None:
            return {"text": "По вашим оценкам и отметкам произведений.", "source_work": None}
        work = entry.work if entry.work_id else entry.private_work
        verb = {
            "rating": "По содержанию оценённого произведения",
            "context": "По содержанию произведения с положительными отметками",
        }.get(source, "Вам понравилось")
        return {
            "text": f"{verb} «{work.title}»: {tag.name}.",
            "source_work": {"id": work.id, "scope": "catalog" if entry.work_id else "private", "title": work.title},
        }

    def list(self, user_id, filters):
        rows, total, mode = self.queries.page(user_id, filters)
        return {
            "items": [{"work": work_card(row), "reason": self.reason(user_id, row.id, mode)} for row in rows],
            "total": total,
            "mode": mode,
        }

    def hide(self, user_id, work_id, hidden):
        self.library.lock_user(user_id)
        self.works.get_work(work_id)
        if hidden:
            self.db.execute(insert(Hidden).values(user_id=user_id, work_id=work_id).on_conflict_do_nothing())
        else:
            self.db.execute(delete(Hidden).where(Hidden.user_id == user_id, Hidden.work_id == work_id))
        self.db.commit()

    def hidden(self, user_id, filters):
        query = select(Work).join(Hidden, Hidden.work_id == Work.id).where(Hidden.user_id == user_id)
        rows, total = self.works.page(self.works.ordered(query, "title_asc"), filters)
        entries = self.works.entries(user_id, [row.id for row in rows])
        return {"items": [catalog_card(row, entries.get(row.id)) for row in rows], "total": total}

    def similar(self, user_id, work_id, filters, *, private=False):
        self.works.validate_filters(filters)
        if private:
            work = self.works.get_private(work_id, user_id)
            entry = self.library.get_private_entry(work_id, user_id)
            tags = [row.tag for row in entry.signals if row.value > 0 and row.source in ("review", "manual")]
        else:
            work = self.works.get_work(work_id)
            tags = work.tags
        basis = "tags" if tags else "genres" if work.genres else "none"
        if basis == "none":
            return {"items": [], "total": 0, "basis": basis}
        source = {row.id: row.name for row in (tags if tags else work.genres)}
        rows, total = self.queries.similar(user_id, work_id, list(source), basis, filters)
        items = []
        for row in rows:
            matches = sorted(source[t.id] for t in (row.tags if basis == "tags" else row.genres) if t.id in source)
            label = "признаки" if basis == "tags" else "жанры"
            items.append(
                {"work": work_card(row), "reason": {"text": f"Похожие {label} с «{work.title}»: {', '.join(matches)}."}}
            )
        return {"items": items, "total": total, "basis": basis}
