from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import Library, Tag, WorkTag
from app.db.queries.library import LibraryQueries
from app.db.queries.preferences import PreferencesQueries
from app.db.queries.works import WorksQueries
from app.services.presenters import analysis_response, entry_response

REVIEW_FIELDS = ("liked", "disliked", "comment")
RATING_VALUES = {1: Decimal("-.3"), 2: Decimal("-.2"), 4: Decimal(".2"), 5: Decimal(".3")}


class LibraryService:
    def __init__(self, db: Session):
        self.db = db
        self.queries = LibraryQueries(db)
        self.works = WorksQueries(db)
        self.preferences = PreferencesQueries(db)

    def get(self, user_id, entry_id):
        return entry_response(self.queries.get_entry(entry_id, user_id), include_work=True)

    def list(self, user_id, filters):
        rows, total = self.works.page(self.queries.filtered(user_id, filters), filters)
        return {"items": [entry_response(row, include_work=True) for row in rows], "total": total}

    def rating_signals(self, entry):
        value = RATING_VALUES.get(entry.rating)
        if value is None or entry.work_id is None:
            return []
        ids = self.db.scalars(select(WorkTag.tag_id).where(WorkTag.work_id == entry.work_id, WorkTag.is_main))
        return [{"tag_id": tag_id, "value": value, "source": "rating", "quote": None} for tag_id in ids]

    def apply_feedback(self, entry, values):
        old_text = tuple(getattr(entry, field) for field in REVIEW_FIELDS)
        current_manual = [
            {"tag_id": row.tag_id, "value": int(row.value)} for row in entry.signals if row.source == "manual"
        ]
        manual = values.get("manual_tags", current_manual)
        self.works.references(Tag, [row["tag_id"] for row in manual])
        new_text = tuple(values.get(field, getattr(entry, field)) for field in REVIEW_FIELDS)
        if sum(len(value or "") for value in new_text) > 5000:
            raise ApiError(422, "VALIDATION_ERROR", "Отзыв должен быть не длиннее 5000 символов")
        if any(new_text) and manual:
            raise ApiError(422, "FEEDBACK_CONFLICT", "Отзыв и ручные отметки нельзя сохранить одновременно")
        for field, value in values.items():
            if field != "manual_tags":
                setattr(entry, field, value)
        if new_text != old_text:
            entry.version += 1
            entry.analysis = "pending" if any(new_text) else None
            signals = []
        else:
            signals = [
                {"tag_id": row.tag_id, "value": row.value, "source": row.source, "quote": row.quote}
                for row in entry.signals
                if row.source == "review"
            ]
        if not any(new_text):
            entry.analysis = None
            signals = [
                {"tag_id": row["tag_id"], "value": row["value"], "source": "manual", "quote": None} for row in manual
            ]
        if not signals and (entry.analysis is None or entry.analysis == "done"):
            signals = self.rating_signals(entry)
        self.preferences.replace_signals(entry, signals)

    def create_entry(self, user_id, values, *, work_id=None, private_id=None):
        entry = Library(user_id=user_id, work_id=work_id, private_id=private_id, status="planned", version=0)
        self.db.add(entry)
        self.db.flush()
        self.apply_feedback(entry, values)
        return entry

    def create(self, user_id, body):
        self.queries.lock_user(user_id)
        self.works.get_work(body.work_id)
        existing = self.db.scalar(select(Library).where(Library.user_id == user_id, Library.work_id == body.work_id))
        if existing is not None:
            raise ApiError(409, "ALREADY_IN_LIBRARY", "Уже в библиотеке", details={"library_id": str(existing.id)})
        before = self.preferences.state(user_id)
        entry = self.create_entry(user_id, body.model_dump(exclude={"work_id"}), work_id=body.work_id)
        self.preferences.rescore_if_changed(user_id, before)
        self.db.commit()
        return entry_response(entry, include_work=True)

    def update(self, user_id, entry_id, values):
        self.queries.lock_user(user_id)
        entry = self.queries.get_entry(entry_id, user_id, lock=True)
        before = self.preferences.state(user_id)
        self.apply_feedback(entry, values)
        self.preferences.rescore_if_changed(user_id, before)
        self.db.commit()
        return entry_response(entry, include_work=True)

    def delete(self, user_id, entry_id):
        from app.services.covers import CoversService

        self.queries.lock_user(user_id)
        entry = self.queries.get_entry(entry_id, user_id, lock=True)
        before = self.preferences.state(user_id)
        private = entry.private_work
        cover = private.cover if private else None
        self.preferences.replace_signals(entry, [])
        self.db.delete(entry)
        self.db.flush()
        if private:
            self.db.delete(private)
        self.preferences.rescore_if_changed(user_id, before)
        self.db.commit()
        CoversService.remove_file(cover)

    def retry(self, user_id, entry_id):
        self.queries.lock_user(user_id)
        entry = self.queries.get_entry(entry_id, user_id, lock=True)
        if entry.analysis != "error" or not any(getattr(entry, field) for field in REVIEW_FIELDS):
            raise ApiError(409, "ANALYSIS_NOT_RETRYABLE", "Повтор доступен после ошибки анализа")
        entry.analysis = "pending"
        entry.version += 1
        self.db.commit()
        return analysis_response(entry)
