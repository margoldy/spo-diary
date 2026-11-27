import io
import logging
import warnings
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select

from app.core.config import APP_DIR, get_settings
from app.core.errors import ApiError
from app.db.models import PrivateWork
from app.db.queries.library import LibraryQueries
from app.db.queries.works import WorksQueries
from app.services.presenters import cover_url

logger = logging.getLogger(__name__)
MAX_BYTES = 10_485_760
CATALOG_DIR = APP_DIR / "covers" / "catalog"


class CoversService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def path(key):
        if key.startswith("catalog/"):
            root = CATALOG_DIR.resolve()
            relative = key.removeprefix("catalog/")
        elif key.startswith("private/"):
            root = (get_settings().storage_dir / "private").resolve()
            relative = key.removeprefix("private/")
        else:
            raise ApiError(404, "COVER_NOT_FOUND", "Обложка не найдена")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ApiError(404, "COVER_NOT_FOUND", "Обложка не найдена")
        return path

    @staticmethod
    def remove_file(key):
        if key and key.startswith("private/"):
            try:
                CoversService.path(key).unlink(missing_ok=True)
            except OSError:
                logger.warning("Не удалось удалить неиспользуемую обложку")

    @staticmethod
    def save(data):
        if len(data) > MAX_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE", "Файл больше 10 МиБ")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as source:
                    if source.format not in ("JPEG", "PNG", "WEBP"):
                        raise ApiError(415, "UNSUPPORTED_IMAGE", "Нужен JPEG, PNG или WebP")
                    if (
                        getattr(source, "is_animated", False)
                        or max(source.size) > 8000
                        or source.width * source.height > 20_000_000
                    ):
                        raise ApiError(422, "INVALID_IMAGE", "Недопустимые размеры или анимация")
                    source.load()
                    converted = ImageOps.exif_transpose(source).convert("RGB")
                    converted.thumbnail((800, 1200))
                    key = f"private/{uuid4().hex}.webp"
                    path = CoversService.path(key)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    converted.save(path, "WEBP", quality=80)
                    return key
        except UnidentifiedImageError:
            known_header = data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8")) or (
                data.startswith(b"RIFF") and data[8:12] == b"WEBP"
            )
            if known_header:
                raise ApiError(422, "INVALID_IMAGE", "Повреждённое изображение") from None
            raise ApiError(415, "UNSUPPORTED_IMAGE", "Нужен JPEG, PNG или WebP") from None
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ApiError(422, "INVALID_IMAGE", "Повреждённое изображение") from None

    def get(self, user_id, work_id, *, private=False):
        queries = WorksQueries(self.db)
        work = queries.get_private(work_id, user_id) if private else queries.get_work(work_id)
        if not work.cover:
            raise ApiError(404, "COVER_NOT_FOUND", "Обложка не найдена")
        try:
            return self.path(work.cover).read_bytes()
        except OSError:
            raise ApiError(404, "COVER_NOT_FOUND", "Обложка не найдена") from None

    def replace(self, user_id, work_id, data=None):
        LibraryQueries(self.db).lock_user(user_id)
        work = WorksQueries(self.db).get_private(work_id, user_id)
        old = work.cover
        new = self.save(data) if data is not None else None
        try:
            work.cover = new
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.remove_file(new)
            raise
        self.remove_file(old)
        return {"cover_url": cover_url(work)}

    def cleanup(self):
        """удаляем личные обложки без привязки старше суток"""
        import time

        used = set(self.db.scalars(select(PrivateWork.cover).where(PrivateWork.cover.is_not(None))))
        root = get_settings().storage_dir.resolve()
        private = root / "private"
        if private.is_dir():
            for path in private.rglob("*.webp"):
                key = path.relative_to(root).as_posix()
                if key not in used and path.stat().st_mtime < time.time() - 86400:
                    self.remove_file(key)
