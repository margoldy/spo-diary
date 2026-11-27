from pathlib import PurePosixPath

from app.core.reference import TYPE_CODES


def reference(row):
    return {"id": row.id, "name": row.name}


def cover_url(work):
    if not work.cover:
        return None
    if hasattr(work, "user_id"):
        return f"/api/v1/me/private-works/{work.id}/cover?v={PurePosixPath(work.cover).stem}"
    return f"/api/v1/works/{work.id}/cover"


def work_card(work):
    return {
        "id": work.id,
        "scope": "private" if hasattr(work, "user_id") else "catalog",
        "title": work.title,
        "type": TYPE_CODES[work.type_id],
        "author": work.author,
        "year": work.year,
        "country": work.country,
        "age_rating": work.age_rating,
        "cover_url": cover_url(work),
        "genres": [reference(row) for row in sorted(work.genres, key=lambda row: (row.name.lower(), row.id))],
    }


def work_detail(work):
    return {
        **work_card(work),
        "description": work.description,
        "tags": [
            reference(row) for row in sorted(getattr(work, "tags", []), key=lambda row: (row.name.lower(), row.id))
        ],
    }


def analysis_response(entry):
    signals = sorted(entry.signals, key=lambda row: row.tag_id)
    return {
        "analysis": {"status": entry.analysis or "none", "version": entry.version},
        "effective_source": signals[0].source if signals else "none",
        "signals": [{"tag": reference(row.tag), "value": float(row.value), "quote": row.quote} for row in signals],
    }


def entry_response(entry, *, include_work=False):
    data = {
        key: getattr(entry, key) for key in ("id", "status", "rating", "liked", "disliked", "comment", "created_at")
    }
    data.update(analysis_response(entry))
    if include_work:
        data["work"] = work_card(entry.work if entry.work_id else entry.private_work)
    return data


def catalog_card(work, entry=None):
    return {
        **work_card(work),
        "library": {key: getattr(entry, key) for key in ("id", "status", "rating")} if entry else None,
    }
