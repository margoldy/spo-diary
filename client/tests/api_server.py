import os
import sys
from pathlib import Path
from unittest.mock import patch

import uvicorn

ROOT = Path(__file__).resolve().parents[2] / "server"
sys.path.insert(0, str(ROOT))
os.environ.update(
    DB_NAME="spo_diary_ui_test",
    COOKIE_SECURE="false",
    JWT_SECRET="frontend-test-secret-never-use-in-production",
    YANDEX_API_KEY="",
    STORAGE_DIR=str(ROOT / ".local/ui-covers"),
)

from app.db.session import get_engine
from data.load import main as load

assert get_engine().url.database == "spo_diary_ui_test"
load()

from sqlalchemy import text
from app.main import app

with get_engine().begin() as db:
    db.execute(text("TRUNCATE users, codes CASCADE"))

# письма и платная модель в браузерных тестах не вызываются
with patch("app.services.auth.send_code"), patch("app.services.auth.secrets.randbelow", return_value=314159):
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
