from decimal import Decimal

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.core.recommendations import ContentScores, catalog_maps
from app.db.models import Library, LibraryTag, Recommendation, UserTag, WorkGenre, WorkTag


class PreferencesQueries:
    def __init__(self, db: Session):
        self.db = db

    def weights(self, user_id):
        return dict(
            self.db.execute(
                select(UserTag.tag_id, UserTag.weight).where(UserTag.user_id == user_id, UserTag.weight != 0)
            ).all()
        )

    def replace_signals(self, entry, signals):
        previous = {
            row.tag_id: row.value
            for row in self.db.scalars(select(LibraryTag).where(LibraryTag.library_id == entry.id))
        }
        current = {row["tag_id"]: Decimal(str(row["value"])) for row in signals}
        for tag_id in previous.keys() | current.keys():
            old, new = previous.get(tag_id, Decimal(0)), current.get(tag_id, Decimal(0))
            if old == new:
                continue
            row = self.db.get(UserTag, (entry.user_id, tag_id))
            if row is None:
                row = UserTag(user_id=entry.user_id, tag_id=tag_id, positive=Decimal(0), negative=Decimal(0))
                self.db.add(row)
            row.positive += max(new, 0) - max(old, 0)
            row.negative += max(-new, 0) - max(-old, 0)
        self.db.execute(delete(LibraryTag).where(LibraryTag.library_id == entry.id))
        self.db.add_all([LibraryTag(library_id=entry.id, **row) for row in signals])
        self.db.flush()
        self.db.expire(entry, ["signals"])
        self.remove_empty(entry.user_id)

    def remove_empty(self, user_id):
        self.db.execute(
            delete(UserTag).where(
                UserTag.user_id == user_id, UserTag.positive == 0, UserTag.negative == 0
            )
        )

    def rescore(self, user_id, work_ids=None):
        condition = Recommendation.user_id == user_id
        if work_ids is not None:
            condition &= Recommendation.work_id.in_(work_ids)
        self.db.execute(delete(Recommendation).where(condition))
        tags, main, genres = catalog_maps(
            self.db.execute(select(WorkTag.work_id, WorkTag.tag_id, WorkTag.is_main)),
            self.db.execute(select(WorkGenre.work_id, WorkGenre.genre_id)),
        )
        profile, ratings = self.context(user_id, genres)
        scorer = ContentScores(tags, main, genres)
        rows = []
        for work_id in tags.keys() if work_ids is None else work_ids:
            if tags[work_id].intersection(profile):
                rows.append({"user_id": user_id, "work_id": work_id, "score": scorer.score(work_id, profile, ratings)})
        if rows:
            self.db.execute(insert(Recommendation), rows)

    def context(self, user_id, genres=None):
        if genres is None:
            _, _, genres = catalog_maps([], self.db.execute(select(WorkGenre.work_id, WorkGenre.genre_id)))
        profile = {
            row.tag_id: (row.positive, row.negative)
            for row in self.db.scalars(select(UserTag).where(UserTag.user_id == user_id))
        }
        ratings = [
            {"tag_id": tag_id, "value": value, "genres": genres[work_id], "work_id": work_id, "library_id": library_id}
            for tag_id, value, work_id, library_id in self.db.execute(
                select(LibraryTag.tag_id, LibraryTag.value, Library.work_id, Library.id)
                .join(Library, Library.id == LibraryTag.library_id)
                .where(Library.user_id == user_id, LibraryTag.source == "rating")
            )
        ]
        return profile, ratings

    def state(self, user_id):
        ratings = tuple(
            self.db.execute(
                select(Library.id, Library.work_id, LibraryTag.tag_id, LibraryTag.value)
                .join(LibraryTag, LibraryTag.library_id == Library.id)
                .where(Library.user_id == user_id, LibraryTag.source == "rating")
                .order_by(Library.id, LibraryTag.tag_id)
            ).all()
        )
        return self.weights(user_id), ratings

    def rescore_if_changed(self, user_id, previous):
        self.db.flush()
        if self.state(user_id) != previous:
            self.rescore(user_id)
