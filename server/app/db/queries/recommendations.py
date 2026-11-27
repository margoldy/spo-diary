from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session

from app.core.recommendations import ContentScores, catalog_maps, explicit_weights
from app.db.models import Library, LibraryTag, Recommendation, Tag, UserTag, Work, WorkGenre, WorkTag
from app.db.queries.preferences import PreferencesQueries
from app.db.queries.works import WorksQueries


class RecommendationsQueries:
    def __init__(self, db: Session):
        self.db = db
        self.works = WorksQueries(db)

    def page(self, user_id, filters):
        base = self.works.available(self.works.filtered(filters), user_id)
        personal = base.join(
            Recommendation, (Recommendation.work_id == Work.id) & (Recommendation.user_id == user_id)
        ).where(Recommendation.score > 0)
        has_personal = self.db.scalar(select(exists(personal.with_only_columns(Work.id))))
        has_preferences = self.db.scalar(select(exists().where(UserTag.user_id == user_id, UserTag.weight > 0)))
        if not has_preferences:
            profile, ratings = PreferencesQueries(self.db).context(user_id)
            has_preferences = any(value > 0 for value in explicit_weights(profile, ratings).values())
        if has_personal or has_preferences:
            query, mode = personal, "personal"
            if filters.sort == "relevance":
                query = query.order_by(Recommendation.score.desc())
        else:
            query, mode = base, "general"
            if filters.sort == "relevance":
                negative = exists(
                    select(WorkTag.tag_id)
                    .join(UserTag, UserTag.tag_id == WorkTag.tag_id)
                    .where(WorkTag.work_id == Work.id, UserTag.user_id == user_id, UserTag.weight < 0)
                )
                query = query.order_by(negative)
        rows, total = self.works.page(self.works.ordered(query, filters.sort), filters)
        return rows, total, mode

    def reason_source(self, user_id, work_id):
        genres = set(self.db.scalars(select(WorkGenre.genre_id).where(WorkGenre.work_id == work_id)))
        tag_map, main_map, genre_map = catalog_maps(
            self.db.execute(select(WorkTag.work_id, WorkTag.tag_id, WorkTag.is_main)),
            self.db.execute(select(WorkGenre.work_id, WorkGenre.genre_id)),
        )
        profile, ratings = PreferencesQueries(self.db).context(user_id, genre_map)
        weights = ContentScores(tag_map, main_map, genre_map).contributions(work_id, profile, ratings)
        tags = list(
            self.db.scalars(select(Tag).join(WorkTag, WorkTag.tag_id == Tag.id).where(WorkTag.work_id == work_id))
        )
        positive = [tag for tag in tags if weights.get(tag.id, 0) > 0]
        if not positive:
            return None, None, None
        tag = min(positive, key=lambda t: (-weights[t.id], t.id))
        is_explicit = explicit_weights(profile, ratings).get(tag.id, 0) > 0
        results = self.db.execute(
            select(Library, LibraryTag.source)
            .join(LibraryTag, LibraryTag.library_id == Library.id)
            .where(Library.user_id == user_id, LibraryTag.tag_id == tag.id, LibraryTag.value > 0)
            .order_by(case((LibraryTag.source == "review", 0), (LibraryTag.source == "manual", 1), else_=2), Library.id)
        ).all()
        for entry, source in results:
            if (source == "rating") == is_explicit:
                continue
            if source == "rating":
                source_genres = {g.id for g in entry.work.genres} if entry.work else set()
                if genres and source_genres and not genres.intersection(source_genres):
                    continue
            return tag, entry, source
        return tag, None, None

    def similar(self, user_id, source_id, ids, basis, filters):
        link, column = (WorkTag, WorkTag.tag_id) if basis == "tags" else (WorkGenre, WorkGenre.genre_id)
        all_count = (
            select(func.count()).select_from(link).where(link.work_id == Work.id).correlate(Work).scalar_subquery()
        )
        intersection = (
            select(func.count())
            .select_from(link)
            .where(link.work_id == Work.id, column.in_(ids))
            .correlate(Work)
            .scalar_subquery()
        )
        score = intersection * 1.0 / (len(ids) + all_count - intersection)
        query = self.works.available(self.works.filtered(filters), user_id).where(
            intersection > 0, Work.id != source_id
        )
        query = query.order_by(score.desc(), func.lower(Work.title), Work.id)
        return self.works.page(query, filters)
