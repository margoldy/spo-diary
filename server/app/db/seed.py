import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.reference import GENRES, TYPE_IDS, TYPES
from app.db.models import Genre, Library, Tag, Type, User, Work, WorkGenre, WorkGroup, WorkTag
from app.db.queries.library import CATALOG_LOCK, LibraryQueries
from app.db.queries.preferences import PreferencesQueries
from app.db.session import get_engine
from app.services.covers import CoversService
from app.services.library import LibraryService

GENRE_NAMES = {name: UUID(key) for key, name in GENRES.items()}
GENRE_MAP = {
    "Морские приключения": ["Приключения"],
    "Исторические приключения": ["Приключения", "Историческое"],
    "Остросюжетные любовные романы": ["Романтика", "Триллер"],
    "Научная фантастика": ["Фантастика"],
    "Социальная фантастика": ["Фантастика"],
    "Классика фантастики": ["Классика", "Фантастика"],
    "Тайна": ["Детектив"],
    "Гурман": ["Повседневность"],
    "Классическая проза": ["Классика"],
    "Детская проза": ["Детская литература"],
}
AGE_RATINGS = {"0+", "6+", "12+", "16+", "18+", "G", "PG", "PG-13", "R", "R+", "R18+"}


def upsert(db, model, values):
    statement = insert(model).values(**values)
    updates = {key: getattr(statement.excluded, key) for key in values if key != "id"}
    statement = (
        statement.on_conflict_do_update(index_elements=["id"], set_=updates)
        if updates
        else statement.on_conflict_do_nothing()
    )
    db.execute(statement)


def seed_references(db):
    for code, name in TYPES.items():
        upsert(db, Type, {"id": TYPE_IDS[code], "name": name})
    for key, name in GENRES.items():
        upsert(db, Genre, {"id": UUID(key), "name": name})
    for row in json.loads(Path(__file__).with_name("tags.json").read_text("utf-8")):
        upsert(db, Tag, {"id": UUID(row["id"]), "name": row["name"]})


def creators(row):
    def value(key):
        result = row.get(key)
        return ", ".join(result) if isinstance(result, list) else result

    if row["type"] in ("movie", "series"):
        return value("director") or value("author")
    if row["type"] in ("anime", "animated_movie", "animated_series"):
        parts = [
            f"{label}: {value(key)}" for key, label in [("director", "Режиссёр"), ("studio", "Студия")] if value(key)
        ]
        return "; ".join(parts) or value("author")
    if row["type"] in ("manga", "manhwa", "manhua", "comic"):
        parts = list(dict.fromkeys(x for x in (value("author"), value("artist")) if x))
        return "; ".join(parts) or None
    return value("author")


def import_catalog(db, path):
    data = json.loads(path.read_text("utf-8"))
    for row in data.get("tags", []):
        upsert(db, Tag, {"id": UUID(row["id"]), "name": row["name"]})
    for row in data.get("work_groups", []):
        upsert(db, WorkGroup, {"id": UUID(row["id"])})
    changed = set()
    for row in data["works"]:
        work_id = UUID(row["id"])
        tag_ids = {UUID(value) for value in row.get("tag_ids", [])}
        main_ids = {UUID(value) for value in row.get("main_tag_ids", row.get("tag_ids", []))}
        if not main_ids.issubset(tag_ids) or (tag_ids and not main_ids):
            raise ValueError("Основные признаки должны быть непустой частью тегов произведения")
        old_tags = dict(db.execute(select(WorkTag.tag_id, WorkTag.is_main).where(WorkTag.work_id == work_id)).all())
        if db.get(Work, work_id) is None or old_tags != {tag: tag in main_ids for tag in tag_ids}:
            changed.add(work_id)
        genre_ids = set()
        for name in row.get("genres", []):
            for normalized in GENRE_MAP.get(name, [name]):
                if normalized not in GENRE_NAMES:
                    raise ValueError(f"Неизвестный жанр: {name}")
                genre_ids.add(GENRE_NAMES[normalized])
        if set(db.scalars(select(WorkGenre.genre_id).where(WorkGenre.work_id == work_id))) != genre_ids:
            changed.add(work_id)
        cover = None
        if row.get("cover"):
            cover = row["cover"]
            if not cover.startswith("catalog/"):
                raise ValueError("Обложка должна находиться в app/covers/catalog")
            source = CoversService.path(cover)
            from PIL import Image

            with Image.open(source) as image:
                if image.format != "WEBP" or getattr(image, "is_animated", False):
                    raise ValueError("Обложка каталога должна быть статичной WebP")
                image.verify()
        values = {key: row.get(key) for key in ("title", "description", "year", "country")}
        values.update(
            id=work_id,
            type_id=TYPE_IDS[row["type"]],
            author=creators(row),
            cover=cover,
            age_rating=row.get("age_rating") if row.get("age_rating") in AGE_RATINGS else None,
            group_id=UUID(row["group_id"]) if row.get("group_id") else None,
        )
        upsert(db, Work, values)
        db.execute(delete(WorkGenre).where(WorkGenre.work_id == work_id))
        db.add_all([WorkGenre(work_id=work_id, genre_id=value) for value in genre_ids])
        if work_id in changed:
            db.execute(delete(WorkTag).where(WorkTag.work_id == work_id))
            db.add_all([WorkTag(work_id=work_id, tag_id=value, is_main=value in main_ids) for value in tag_ids])
    db.flush()
    preferences = PreferencesQueries(db)
    library = LibraryService(db)
    for user_id in db.scalars(select(User.id).order_by(User.id)):
        LibraryQueries(db).lock_user(user_id)
        entries = db.scalars(select(Library).where(Library.user_id == user_id, Library.work_id.in_(changed))).all()
        for entry in entries:
            concrete = any(signal.source in ("review", "manual") for signal in entry.signals)
            if not concrete and entry.analysis in (None, "done"):
                preferences.replace_signals(entry, library.rating_signals(entry))
        if changed:
            preferences.rescore(user_id)
    return len(data["works"])


def load(catalog=None):
    with Session(get_engine()) as db:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CATALOG_LOCK})
        seed_references(db)
        count = import_catalog(db, catalog.resolve()) if catalog else 0
        if not catalog:
            for user_id in db.scalars(select(User.id).order_by(User.id)):
                LibraryQueries(db).lock_user(user_id)
                PreferencesQueries(db).rescore(user_id)
        db.commit()
    return count


def main():
    parser = argparse.ArgumentParser(description="Справочники и импорт подготовленного каталога")
    parser.add_argument("catalog", nargs="?", type=Path)
    args = parser.parse_args()
    count = load(args.catalog)
    print(f"Справочники загружены. Произведений импортировано: {count}.")


if __name__ == "__main__":
    main()
