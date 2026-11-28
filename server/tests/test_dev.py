import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import psycopg
from psycopg import sql

from tests.config import database_env, database_url

ROOT = Path(__file__).resolve().parents[1]


class DevTests(unittest.TestCase):
    def test_shared_configuration_uses_project_paths(self):
        config = ET.parse(ROOT.parent / ".run/Backend.run.xml").find("configuration")
        options = {item.attrib["name"]: item.attrib["value"] for item in config.findall("option")}
        self.assertEqual(options["WORKING_DIRECTORY"], "$PROJECT_DIR$/server")
        self.assertEqual(options["SCRIPT_NAME"], "$PROJECT_DIR$/server/dev.py")
        self.assertEqual(options["SDK_HOME"], "$PROJECT_DIR$/server/app/.venv/Scripts/python.exe")

    def test_start_worker_stop_and_restart(self):
        url = database_url()
        name = "spo_diary_start_test_" + uuid4().hex
        admin_url = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
        with psycopg.connect(admin_url, autocommit=True) as admin:
            try:
                self.check_runs(url.set(database=name))
            finally:
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))

    def check_runs(self, url):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        secret = uuid4().hex + uuid4().hex
        env = dict(
            os.environ,
            **database_env(url),
            API_PORT=str(port),
            JWT_SECRET=secret,
            YANDEX_API_KEY="",
            SMTP_HOST="",
            COOKIE_SECURE="false",
            PYTHONUTF8="1",
        )
        dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
        user_id = uuid4()
        for attempt in range(2):
            with tempfile.TemporaryFile() as log:
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / "dev.py")],
                    cwd=ROOT.parent,
                    env=env,
                    stdout=log,
                    stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    with httpx.Client(
                        base_url=f"http://127.0.0.1:{port}/api/v1",
                        headers={"Origin": "http://127.0.0.1:5173"},
                        timeout=10,
                    ) as client:
                        deadline = time.monotonic() + 60
                        while time.monotonic() < deadline:
                            if process.poll() is not None:
                                log.seek(0)
                                self.fail(log.read().decode("utf-8", errors="replace"))
                            try:
                                if client.get("/me").status_code == 401:
                                    break
                            except httpx.ConnectError:
                                pass
                            time.sleep(.2)
                        else:
                            self.fail("API не запустился")
                        if not attempt:
                            with psycopg.connect(dsn) as db:
                                db.execute(
                                    "INSERT INTO users(id,email,name) VALUES (%s,%s,%s)",
                                    (user_id, "dev@example.com", "Проверка"),
                                )
                        now = datetime.now(timezone.utc)
                        token = jwt.encode(
                            {"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(minutes=5)},
                            secret,
                            algorithm="HS256",
                        )
                        client.cookies.set("access_token", token)
                        catalog = client.get("/works").json()
                        self.assertEqual(catalog["total"], 202)
                        cover_path = catalog["items"][0]["cover_url"].removeprefix("/api/v1")
                        self.assertEqual(client.get(cover_path).status_code, 200)
                        if not attempt:
                            created = client.post(
                                "/me/library",
                                json={"work_id": catalog["items"][0]["id"], "comment": "Тест без платной модели"},
                            )
                            self.assertEqual(created.status_code, 201)
                            entry_id = created.json()["id"]
                            deadline = time.monotonic() + 30
                            while time.monotonic() < deadline:
                                if client.get(f"/me/library/{entry_id}").json()["analysis"]["status"] == "error":
                                    break
                                time.sleep(.2)
                            else:
                                self.fail("Обработчик не забрал отзыв")
                        else:
                            self.assertEqual(client.get("/me/library").json()["total"], 1)
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=15)
                with psycopg.connect(dsn, autocommit=True) as db:
                    self.assertTrue(db.execute("SELECT pg_try_advisory_lock(738422)").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
