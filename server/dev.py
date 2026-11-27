import logging
import os
import threading
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def serve(port):
    from app.worker import main as worker

    server = uvicorn.Server(uvicorn.Config("app.main:app", host="127.0.0.1", port=port))
    stopped = threading.Event()
    errors = []

    def run_worker():
        try:
            worker(stopped)
        except BaseException as error:
            if not stopped.is_set():
                errors.append(error)
                logger.error("Обработчик остановлен (%s)", type(error).__name__)
                server.should_exit = True

    thread = threading.Thread(target=run_worker, name="review-worker", daemon=True)
    thread.start()
    try:
        server.run()
    finally:
        stopped.set()
        thread.join(timeout=5)
    if errors:
        raise SystemExit("Обработчик отзывов завершился с ошибкой.")


def main():
    env = ROOT / "app/.env"
    if not env.is_file():
        raise SystemExit("Файл app/.env отсутствует.")
    values = dotenv_values(env)
    try:
        port = int(os.environ.get("API_PORT") or values.get("API_PORT") or 8000)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("API_PORT должен быть числом от 1 до 65535.") from None
    from data.load import main as load

    load()
    print(f"API: http://127.0.0.1:{port}/api/v1", flush=True)
    serve(port)


if __name__ == "__main__":
    main()
