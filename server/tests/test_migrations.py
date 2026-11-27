import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

from tests.config import database_env, database_url

ROOT = Path(__file__).resolve().parents[1]


class MigrationTests(unittest.TestCase):
    def test_removing_choices_preserves_feedback_and_rebuilds_scores(self):
        url = database_url().set(database="spo_diary_migration_test_" + uuid4().hex)
        admin_url = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
            try:
                self.check_upgrade(url)
            finally:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(url.database)))

    def check_upgrade(self, url):
        env = dict(os.environ, **database_env(url), JWT_SECRET=uuid4().hex, YANDEX_API_KEY="", SMTP_HOST="")

        def migrate(target):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", target], cwd=ROOT, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        migrate("75ad152fc932")
        dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
        user, type_id, tag, empty_tag, source, target, entry = [uuid4() for _ in range(7)]
        with psycopg.connect(dsn) as db:
            db.execute("INSERT INTO users(id,email,name) VALUES (%s,'migration@example.com','Тест')", (user,))
            db.execute("INSERT INTO types(id,name) VALUES (%s,'Книга')", (type_id,))
            for tag_id, name in ((tag, "Дружба"), (empty_tag, "Только начальный выбор")):
                db.execute("INSERT INTO tags(id,name) VALUES (%s,%s)", (tag_id, name))
            for work in (source, target):
                db.execute("INSERT INTO works(id,title,type_id) VALUES (%s,'Книга',%s)", (work, type_id))
                db.execute("INSERT INTO work_tags(work_id,tag_id) VALUES (%s,%s)", (work, tag))
            db.execute("INSERT INTO library(id,user_id,work_id) VALUES (%s,%s,%s)", (entry, user, source))
            db.execute("INSERT INTO library_tags(library_id,tag_id,value,source) VALUES (%s,%s,1,'manual')", (entry, tag))
            db.execute("INSERT INTO user_tags(user_id,tag_id,positive,choice) VALUES (%s,%s,1,-1)", (user, tag))
            db.execute("INSERT INTO user_tags(user_id,tag_id,choice) VALUES (%s,%s,1)", (user, empty_tag))
            db.execute("INSERT INTO recommendations(user_id,work_id,score) VALUES (%s,%s,999)", (user, target))
        migrate("head")
        with psycopg.connect(dsn) as db:
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='user_tags'"
            )}
            self.assertNotIn("choice", columns)
            self.assertEqual(db.execute("SELECT count(*) FROM library_tags").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM user_tags").fetchone()[0], 1)
            positive, negative, weight = db.execute("SELECT positive,negative,weight FROM user_tags").fetchone()
            self.assertEqual((positive, negative), (1, 0))
            self.assertAlmostEqual(float(weight), 1 / 3)
            score = db.execute("SELECT score FROM recommendations WHERE work_id=%s", (target,)).fetchone()[0]
            self.assertAlmostEqual(float(score), 1 / 3)


if __name__ == "__main__":
    unittest.main()
