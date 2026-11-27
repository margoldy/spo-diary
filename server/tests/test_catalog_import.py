import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

from tests.config import database_env, database_url

ROOT = Path(__file__).resolve().parents[1]


class CatalogImportTests(unittest.TestCase):
    def test_empty_database_and_repository_copy(self):
        url = database_url()
        name = "spo_diary_import_test_" + uuid4().hex
        admin_url = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            try:
                self.check_copy(url.set(database=name))
            finally:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))

    def check_copy(self, url):
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="catalog-clone-", dir=local) as directory:
            temporary = Path(directory).resolve()
            self.assertTrue(temporary.is_relative_to(local.resolve()))
            clone = temporary / "server"
            clone.mkdir()
            for folder in ("app", "migrations", "data"):
                shutil.copytree(
                    ROOT / folder,
                    clone / folder,
                    ignore=shutil.ignore_patterns(".venv", "__pycache__", ".env", ".env.*", "private"),
                )
            shutil.copyfile(ROOT / "alembic.ini", clone / "alembic.ini")
            env = dict(
                os.environ,
                **database_env(url),
                JWT_SECRET="catalog-import-test-" + uuid4().hex,
                STORAGE_DIR=str(clone / ".local/covers"),
                COOKIE_SECURE="false",
                YANDEX_API_KEY="",
                SMTP_HOST="",
                PYTHONUTF8="1",
            )
            env.pop("PYTHONPATH", None)

            def run(*arguments):
                result = subprocess.run(
                    [sys.executable, *arguments],
                    cwd=temporary,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=120,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            run(str(clone / "data/load.py"))
            # проверяем выдачу файлов через api
            run(
                "-c",
                """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import create_token
from app.db.models import User, Work
from app.db.session import get_engine
from app.main import app
root = Path(sys.argv[1])
data = json.loads((root / 'data/works.json').read_text('utf-8'))
with Session(get_engine()) as db:
    user = User(email='import-check@example.com', name='Проверка импорта')
    db.add(user)
    db.commit()
    token = create_token(user.id)
    assert len(list(db.scalars(select(Work)))) == len(data['works'])
with TestClient(app, headers={'Origin':'http://127.0.0.1:8000'}) as client:
    client.cookies.set('access_token', token)
    for work in data['works']:
        response = client.get('/api/v1/works/' + work['id'] + '/cover')
        assert response.status_code == 200, response.text
        assert response.content == (root / 'app/covers' / work['cover']).read_bytes()
    wid = data['works'][0]['id']
    response = client.post('/api/v1/me/library', json={'work_id':wid, 'status':'completed'})
    assert response.status_code == 201, response.text
    for offset in (0, 100, 200):
        result = client.get(f'/api/v1/me/recommendations?limit=100&offset={offset}').json()
        assert all(item['work']['id'] != wid for item in result['items'])
""",
                str(clone),
            )
            run(str(clone / "data/load.py"))
            self.assertFalse((clone / ".local/covers/catalog").exists())
            self.assertFalse((clone / "data/covers").exists())
            with psycopg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM works").fetchone()[0], 202)
                self.assertEqual(db.execute("SELECT count(*) FROM work_tags").fetchone()[0], 1228)
                self.assertEqual(db.execute("SELECT count(*) FROM work_tags WHERE is_main").fetchone()[0], 594)
                self.assertEqual(db.execute("SELECT count(*) FROM work_groups").fetchone()[0], 34)
                self.assertEqual(db.execute("SELECT count(*) FROM library").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0], 1)
