import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.core.model import ReviewModel
from app.db.models import Code
from app.db.session import get_engine
from app.services.analysis import AnalysisService
from app.services.covers import CoversService

logger = logging.getLogger(__name__)
WORKER_LOCK = 738422


def main(stop_event=None):
    stop_event = stop_event if stop_event is not None else threading.Event()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    engine = get_engine()
    model = ReviewModel()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as guard:
        if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}):
            raise SystemExit("Обработчик уже запущен")
        try:
            with Session(engine) as db:
                AnalysisService(db).recover()
            last_cleanup = 0
            while not stop_event.is_set():
                guard.execute(text("SELECT 1"))
                if time.monotonic() - last_cleanup > 3600:
                    with Session(engine) as db:
                        db.execute(delete(Code).where(Code.expires_at < datetime.now(timezone.utc)))
                        CoversService(db).cleanup()
                        db.commit()
                    last_cleanup = time.monotonic()
                with Session(engine) as db:
                    job = AnalysisService(db).claim()
                if job is None:
                    stop_event.wait(1)
                    continue
                try:
                    signals = model.analyze(job["texts"], job["tags"])
                except Exception as error:
                    logger.warning("Анализ %s не выполнен (%s)", job["id"], type(error).__name__)
                    with Session(engine) as db:
                        AnalysisService(db).apply(job, error=True)
                else:
                    with Session(engine) as db:
                        AnalysisService(db).apply(job, signals)
        except KeyboardInterrupt:
            logger.info("Обработчик остановлен")
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})


if __name__ == "__main__":
    main()
