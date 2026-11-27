from sqlalchemy import select

from app.core.errors import ApiError
from app.db.models import Library, Tag
from app.db.queries.library import LibraryQueries
from app.db.queries.preferences import PreferencesQueries
from app.services.library import REVIEW_FIELDS, LibraryService


class AnalysisService:
    def __init__(self, db):
        self.db = db
        self.library = LibraryQueries(db)
        self.preferences = PreferencesQueries(db)

    def claim(self):
        candidate = self.db.execute(
            select(Library.id, Library.user_id)
            .where(Library.analysis == "pending")
            .order_by(Library.created_at, Library.id)
            .limit(1)
        ).first()
        if candidate is None:
            return None
        self.library.lock_user(candidate.user_id)
        entry = self.db.scalar(
            select(Library)
            .where(Library.id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if entry is None or entry.analysis != "pending":
            return None
        entry.analysis = "running"
        job = {
            "id": entry.id,
            "user_id": entry.user_id,
            "version": entry.version,
            "texts": {field: getattr(entry, field) for field in REVIEW_FIELDS},
            "tags": [{"id": str(row.id), "name": row.name} for row in self.db.scalars(select(Tag).order_by(Tag.id))],
        }
        self.db.commit()
        return job

    def apply(self, job, signals=None, *, error=False):
        try:
            self.library.lock_user(job["user_id"])
        except ApiError as exc:
            if exc.status == 401:
                return False
            raise
        entry = self.db.scalar(
            select(Library)
            .where(Library.id == job["id"], Library.user_id == job["user_id"])
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if entry is None or entry.version != job["version"] or entry.analysis != "running":
            return False
        before = self.preferences.state(entry.user_id)
        entry.analysis = "error" if error else "done"
        actual = [] if error else signals or LibraryService(self.db).rating_signals(entry)
        self.preferences.replace_signals(entry, actual)
        self.preferences.rescore_if_changed(entry.user_id, before)
        self.db.commit()
        return True

    def recover(self):
        candidates = self.db.execute(select(Library.id, Library.user_id).where(Library.analysis == "running")).all()
        self.db.rollback()
        for candidate in candidates:
            self.library.lock_user(candidate.user_id)
            entry = self.db.scalar(select(Library).where(Library.id == candidate.id).with_for_update())
            if entry is not None and entry.analysis == "running":
                entry.analysis = "pending"
                entry.version += 1
            self.db.commit()
