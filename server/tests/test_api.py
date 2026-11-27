import io
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from psycopg import sql
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.config import database_env, database_url

ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = database_url().set(database="spo_diary_test")
TEST_URL = TEST_DATABASE.render_as_string(hide_password=False)
os.environ.update(database_env(TEST_DATABASE))
os.environ["COOKIE_SECURE"] = "false"
os.environ["STORAGE_DIR"] = str(ROOT / ".local/test-covers")

from app.core.config import get_settings
from app.core.limits import limiter
from app.core.model import ReviewModel
from app.core.reference import GENRES, TYPE_IDS
from app.core.security import create_token
from app.db.models import (
    Code,
    Library,
    PrivateWork,
    Tag,
    User,
    UserTag,
    Work,
    WorkGenre,
    WorkGroup,
    WorkTag,
)
from app.db.seed import seed_references
from app.db.session import get_engine
from app.main import app
from app.services.analysis import AnalysisService
from app.services.library import LibraryService

ORIGIN = "http://127.0.0.1:8000"


class ApiFixture(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        get_engine().dispose()

    @classmethod
    def setUpClass(cls):
        get_settings.cache_clear()
        get_engine.cache_clear()
        url = TEST_URL.replace("postgresql+psycopg:", "postgresql:")
        with psycopg.connect(url.rsplit("/", 1)[0] + "/postgres", autocommit=True) as connection:
            if not connection.execute("SELECT 1 FROM pg_database WHERE datname='spo_diary_test'").fetchone():
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("spo_diary_test")))
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        with Session(get_engine()) as db:
            seed_references(db)
            db.commit()

    def setUp(self):
        self.assertEqual(get_engine().url.database, "spo_diary_test")
        with Session(get_engine()) as db:
            db.execute(text("TRUNCATE users, works, work_groups, codes CASCADE"))
            tags = list(db.scalars(select(Tag).order_by(Tag.name)))
            self.tags = [row.id for row in tags[:3]]
            self.genre = UUID(next(iter(GENRES)))
            self.user = User(email="first@example.com", name="Первый")
            self.other = User(email="second@example.com", name="Второй")
            group = WorkGroup()
            db.add_all([self.user, self.other, group])
            db.flush()
            self.user_id, self.other_id = self.user.id, self.other.id
            works = [
                Work(title=title, type_id=TYPE_IDS[kind], year=year, group_id=group.id if i < 2 else None)
                for i, (title, kind, year) in enumerate(
                    [
                        ("Альфа", "book", 2020),
                        ("Бета", "anime", 2025),
                        ("Гамма", "manga", None),
                        ("Дельта 100%_", "book", 2018),
                        ("Эпсилон", "book", 2024),
                    ]
                )
            ]
            db.add_all(works)
            db.flush()
            self.works = [row.id for row in works]
            for index, tag_indexes in enumerate([(0, 1), (0,), (1, 2), (), (2,)]):
                db.add_all([WorkTag(work_id=works[index].id, tag_id=self.tags[j]) for j in tag_indexes])
            db.add_all([WorkGenre(work_id=works[i].id, genre_id=self.genre) for i in (0, 1, 3)])
            db.commit()
        limiter.events.clear()
        self.client = TestClient(app, headers={"Origin": ORIGIN})
        self.client.cookies.set("access_token", create_token(self.user_id))

    def tearDown(self):
        self.client.close()

    def request(self, method, path, *, expected=200, **kwargs):
        response = self.client.request(method, "/api/v1" + path, **kwargs)
        self.assertEqual(response.status_code, expected, response.text)
        self.assertIn("no-store", response.headers.get("cache-control", ""))
        return response.json() if expected != 204 else None

    def add(self, index=0, **values):
        return self.request("POST", "/me/library", expected=201, json={"work_id": str(self.works[index]), **values})

    def mark_tags(self, tags):
        return self.request(
            "POST", "/me/private-works", expected=201,
            json={"title": "Личная книга", "type": "book", "entry": {"manual_tags": tags}},
        )

    def update(self, entry, **values):
        return self.request("PATCH", f"/me/library/{entry['id']}", json=values)

    def weights(self):
        with Session(get_engine()) as db:
            return {
                row.tag_id: (row.positive, row.negative, row.weight)
                for row in db.scalars(select(UserTag).where(UserTag.user_id == self.user_id))
            }


class ApiTests(ApiFixture):
    def test_auth_codes_one_use_and_profile(self):
        self.client.cookies.clear()
        delivered = []
        with patch("app.services.auth.send_code", side_effect=lambda email, code: delivered.append((email, code))):
            code = self.request("POST", "/auth/request-code", json={"email": " NEW@Example.com "})
            self.assertEqual(delivered[0][0], "new@example.com")
            self.assertNotIn("code", code)
            self.request("POST", "/auth/request-code", json={"email": "new@example.com"}, expected=429)
            result = self.request(
                "POST", "/auth/verify-code", json={"code_id": code["code_id"], "code": delivered[0][1]}
            )
            self.assertTrue(result["is_new_user"])
            self.assertEqual(self.request("GET", "/me")["email"], "new@example.com")
            self.request(
                "POST", "/auth/verify-code", json={"code_id": code["code_id"], "code": delivered[0][1]}, expected=422
            )
            self.request("PATCH", "/me", json={"name": " Дарья "})
            self.assertEqual(self.request("GET", "/me")["name"], "Дарья")
            self.request("POST", "/auth/logout", expected=204)
            self.request("GET", "/me", expected=401)

    def test_auth_failures_preserve_attempts_and_old_code(self):
        delivered = []
        with patch("app.services.auth.send_code", side_effect=lambda email, code: delivered.append(code)):
            code = self.request("POST", "/auth/request-code", json={"email": "first@example.com"})
        wrong = "000000" if delivered[0] != "000000" else "999999"
        for i in range(5):
            result = self.request(
                "POST", "/auth/verify-code", json={"code_id": code["code_id"], "code": wrong}, expected=422
            )
            self.assertEqual(result["error"]["details"]["attempts_left"], 4 - i)
        self.request("POST", "/auth/verify-code", json={"code_id": code["code_id"], "code": delivered[0]}, expected=429)
        with Session(get_engine()) as db:
            row = db.get(Code, UUID(code["code_id"]))
            row.created_at -= timedelta(seconds=61)
            db.commit()
        from app.core.errors import ApiError

        with patch("app.services.auth.send_code", side_effect=ApiError(503, "EMAIL_UNAVAILABLE", "Ошибка")):
            self.request("POST", "/auth/request-code", json={"email": "first@example.com"}, expected=503)
        with Session(get_engine()) as db:
            self.assertIsNotNone(db.get(Code, UUID(code["code_id"])))

    def test_access_origin_and_validation(self):
        self.client.cookies.clear()
        for path in ["/works", "/types", "/genres", "/tags", "/me/library", "/me/recommendations"]:
            self.request("GET", path, expected=401)
        self.client.cookies.set("access_token", create_token(self.user_id))
        self.request("PATCH", "/me", json={"name": "x"}, headers={"Origin": "https://evil.example"}, expected=403)
        self.request("POST", "/me/private-works", json={"title": "x", "type": "game"}, expected=422)
        self.request(
            "POST",
            "/me/private-works",
            json={"title": "x", "type": "book", "user_id": str(self.other_id)},
            expected=422,
        )
        self.request("GET", "/works?unknown=1", expected=422)
        self.request("GET", "/works?limit=0", expected=422)
        self.request("GET", "/works?sort=title_asc&sort=year_desc", expected=422)
        self.request("GET", "/me", content=b"{}", expected=422)
        self.request("POST", "/me/private-works", json={"title": "x", "type": "book", "entry": None}, expected=422)
        self.request(
            "POST", "/me/private-works", json={"title": "x", "type": "book", "entry": {"rating": True}}, expected=422
        )

    def test_catalog_filters_adaptations_and_references(self):
        self.assertEqual(len(self.request("GET", "/types")["items"]), 14)
        self.assertEqual(len(self.request("GET", "/genres")["items"]), 26)
        self.assertEqual(self.request("GET", "/tags?limit=2")["total"], 132)
        detail = self.request("GET", f"/works/{self.works[0]}")
        self.assertEqual([x["id"] for x in detail["adaptations"]], [str(self.works[1])])
        self.assertEqual(self.request("GET", "/works?q=%25_")["total"], 1)
        self.assertEqual(self.request("GET", "/works?types=book&types=anime")["total"], 4)
        self.assertEqual(self.request("GET", f"/works?tag_ids={self.tags[0]}&tag_ids={self.tags[1]}")["total"], 1)
        self.request("GET", f"/works?tag_ids={self.tags[0]}&exclude_tag_ids={self.tags[0]}", expected=422)
        self.request("GET", f"/works?genre_ids={uuid4()}", expected=422)
        result = self.request("GET", "/works?sort=year_desc")
        self.assertEqual(result["items"][-1]["id"], str(self.works[2]))
        self.request("GET", f"/works/{self.works[0]}/cover", expected=404)

    def test_library_rating_manual_and_no_recompute_on_reads(self):
        entry = self.add(rating=5)
        self.assertEqual(entry["effective_source"], "rating")
        self.assertEqual(self.weights()[self.tags[0]][0], Decimal(".3"))
        self.request("POST", "/me/library", json={"work_id": str(self.works[0])}, expected=409)
        with patch(
            "app.db.queries.preferences.PreferencesQueries.rescore", side_effect=AssertionError("Лишний пересчёт")
        ):
            self.request("GET", "/me/recommendations")
            self.update(entry, status="completed")
            self.update(entry, rating=5)
            self.request("PUT", f"/me/hidden/{self.works[1]}", expected=204)
            self.request("DELETE", f"/me/hidden/{self.works[1]}", expected=204)
        updated = self.update(entry, manual_tags=[{"tag_id": str(self.tags[2]), "value": -1}])
        self.assertEqual(updated["effective_source"], "manual")
        self.assertEqual(set(self.weights()), {self.tags[2]})
        self.assertEqual(self.weights()[self.tags[2]][1], 1)
        self.request("DELETE", f"/me/library/{entry['id']}", expected=204)
        self.assertEqual(self.weights(), {})

    def test_review_transitions_stale_response_empty_and_neutral(self):
        entry = self.add(rating=5, manual_tags=[{"tag_id": str(self.tags[2]), "value": 1}])
        self.request("PATCH", f"/me/library/{entry['id']}", json={"liked": "Герой"}, expected=422)
        entry = self.update(entry, liked=" Герой ", manual_tags=[])
        self.assertEqual(entry["analysis"], {"status": "pending", "version": 1})
        self.assertEqual(self.weights(), {})
        with Session(get_engine()) as db:
            old = AnalysisService(db).claim()
        entry = self.update(entry, disliked="Юмор")
        with Session(get_engine()) as db:
            self.assertFalse(AnalysisService(db).apply(old, []))
            current = AnalysisService(db).claim()
        with Session(get_engine()) as db:
            AnalysisService(db).apply(
                current, [{"tag_id": self.tags[2], "value": 0, "source": "review", "quote": "Герой"}]
            )
        self.assertEqual(self.request("GET", f"/me/library/{entry['id']}/analysis")["effective_source"], "review")
        self.assertEqual(self.weights(), {})
        entry = self.update(entry, comment="Проверка")
        with Session(get_engine()) as db:
            current = AnalysisService(db).claim()
        with Session(get_engine()) as db:
            AnalysisService(db).apply(current, [])
        self.assertEqual(self.request("GET", f"/me/library/{entry['id']}")["effective_source"], "rating")
        entry = self.update(entry, liked=None, disliked=None, comment=None)
        self.assertEqual(entry["analysis"]["status"], "none")
        self.assertEqual(entry["analysis"]["version"], 4)

    def test_model_observations_are_saved_once(self):
        entry = self.add(rating=5, liked="Герой понравился.", disliked="Но герой раздражает.")
        with Session(get_engine()) as db:
            job = AnalysisService(db).claim()
        _, tags, evidence = ReviewModel.prepare(job["texts"], job["tags"])
        tag = next(i for i, row in enumerate(tags, 1) if row["id"] == str(self.tags[0]))
        observations = [
            {"tag": tag, "evidence": 1, "sentiment": "positive"},
            {"tag": tag, "evidence": 2, "sentiment": "negative"},
        ]
        signals = ReviewModel.normalize(json.dumps({"observations": observations * 2}), job["texts"], tags, evidence)
        with Session(get_engine()) as db:
            self.assertTrue(AnalysisService(db).apply(job, signals))
        result = self.request("GET", f"/me/library/{entry['id']}")
        self.assertEqual(result["effective_source"], "review")
        self.assertEqual(result["analysis"]["status"], "done")
        self.assertEqual(len(result["signals"]), 1)
        self.assertEqual(result["signals"][0]["value"], 0)
        self.assertEqual(result["signals"][0]["quote"], "Герой понравился.")
        self.assertEqual(self.weights(), {})
        self.update(entry, rating=1)
        with Session(get_engine()) as db:
            self.assertIsNone(AnalysisService(db).claim())
        self.assertEqual(self.weights(), {})

    def test_analysis_error_retry_and_restart(self):
        entry = self.add(liked="Текст")
        with Session(get_engine()) as db:
            job = AnalysisService(db).claim()
        with Session(get_engine()) as db:
            AnalysisService(db).apply(job, error=True)
        self.request("GET", f"/me/library/{entry['id']}/analysis")
        retried = self.request("POST", f"/me/library/{entry['id']}/analysis/retry", expected=202)
        self.assertEqual(retried["analysis"]["version"], 2)
        self.request("POST", f"/me/library/{entry['id']}/analysis/retry", expected=409)
        with Session(get_engine()) as db:
            AnalysisService(db).claim()
        with Session(get_engine()) as db:
            AnalysisService(db).recover()
        self.assertEqual(
            self.request("GET", f"/me/library/{entry['id']}/analysis")["analysis"], {"status": "pending", "version": 3}
        )

    def test_private_work_optional_fields_ownership_cover_and_delete(self):
        entry = self.request("POST", "/me/private-works", expected=201, json={"title": "Своя книга", "type": "book"})
        work_id = entry["work"]["id"]
        entry_id = entry["id"]
        self.assertIsNone(entry["work"]["author"])
        self.assertEqual(entry["status"], "planned")
        self.request("PATCH", f"/me/library/{entry_id}", json={"rating": 5})
        self.assertEqual(self.weights(), {})
        self.request(
            "PATCH",
            f"/me/private-works/{work_id}",
            json={"genre_ids": [str(self.genre)], "country": "Россия", "description": "Описание"},
        )
        detail = self.request("GET", f"/me/private-works/{work_id}")
        self.assertEqual(detail["work"]["country"], "Россия")
        self.assertEqual(detail["work"]["tags"], [])
        cleared = self.request(
            "PATCH", f"/me/private-works/{work_id}", json={"country": None, "description": "   ", "author": None}
        )
        self.assertIsNone(cleared["work"]["description"])
        self.assertIsNone(cleared["work"]["country"])
        image = io.BytesIO()
        Image.new("RGB", (30, 40), "red").save(image, "PNG")
        uploaded = self.request(
            "PUT", f"/me/private-works/{work_id}/cover", files={"file": ("cover.png", image.getvalue(), "image/png")}
        )
        response = self.client.get(uploaded["cover_url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.client.cookies.set("access_token", create_token(self.other_id))
        for path in [
            f"/me/private-works/{work_id}",
            f"/me/library/{entry_id}",
            f"/me/private-works/{work_id}/cover",
            f"/me/private-works/{work_id}/similar",
        ]:
            self.request("GET", path, expected=404)
        self.client.cookies.set("access_token", create_token(self.user_id))
        self.request("DELETE", f"/me/private-works/{work_id}/cover", expected=204)
        self.request("DELETE", f"/me/private-works/{work_id}/cover", expected=204)
        self.request("DELETE", f"/me/library/{entry_id}", expected=204)
        with Session(get_engine()) as db:
            self.assertIsNone(db.get(PrivateWork, UUID(work_id)))

    def test_recommendations_feedback_exclusions_filters_and_pagination(self):
        feedback = self.mark_tags([{"tag_id": str(self.tags[0]), "value": 1}])
        data = self.request("GET", "/me/recommendations")
        self.assertEqual(data["mode"], "personal")
        self.assertEqual(data["items"][0]["work"]["id"], str(self.works[1]))
        empty = self.request("GET", "/me/recommendations?offset=99")
        self.assertEqual(empty["mode"], "personal")
        self.assertEqual(empty["items"], [])
        self.assertEqual(self.request("GET", "/me/recommendations?types=manga")["mode"], "personal")
        self.assertEqual(self.request("GET", "/me/recommendations?types=manga")["items"], [])
        for state in ("planned", "in_progress", "completed", "dropped"):
            with Session(get_engine()) as db:
                existing = db.scalar(select(Library).where(Library.work_id == self.works[1]))
            if existing is None:
                self.add(1, status=state)
            else:
                self.update({"id": str(existing.id)}, status=state)
            self.assertNotIn(
                str(self.works[1]), [r["work"]["id"] for r in self.request("GET", "/me/recommendations")["items"]]
            )
        self.request("PUT", f"/me/hidden/{self.works[0]}", expected=204)
        self.assertEqual(self.request("GET", "/me/hidden")["total"], 1)
        self.assertEqual(self.request("GET", "/me/recommendations")["mode"], "personal")
        self.request("DELETE", f"/me/hidden/{self.works[0]}", expected=204)
        self.update(feedback, manual_tags=[])
        general = self.request("GET", "/me/recommendations")
        self.assertEqual(general["mode"], "general")
        self.assertNotIn(str(self.works[1]), [r["work"]["id"] for r in general["items"]])

    def test_similar_tags_genres_and_private(self):
        result = self.request("GET", f"/works/{self.works[0]}/similar")
        self.assertEqual(result["basis"], "tags")
        self.assertEqual(result["items"][0]["work"]["id"], str(self.works[1]))
        result = self.request("GET", f"/works/{self.works[3]}/similar")
        self.assertEqual(result["basis"], "genres")
        entry = self.request("POST", "/me/private-works", expected=201, json={"title": "Своя", "type": "other"})
        work_id = entry["work"]["id"]
        self.assertEqual(self.request("GET", f"/me/private-works/{work_id}/similar")["basis"], "none")
        self.update(entry, manual_tags=[{"tag_id": str(self.tags[2]), "value": 1}])
        self.assertEqual(self.request("GET", f"/me/private-works/{work_id}/similar")["basis"], "tags")

    def test_library_sort_filters_and_feedback_validation(self):
        a = self.add(0, rating=1)
        b = self.add(1, rating=5)
        result = self.request("GET", "/me/library")
        self.assertEqual(result["items"][0]["id"], b["id"])
        self.assertEqual(self.request("GET", "/me/library?sort=rating_desc")["items"][0]["id"], b["id"])
        self.assertEqual(
            self.request("GET", f"/me/library?types=book&genre_ids={self.genre}&statuses=planned")["total"], 1
        )
        self.request("PATCH", f"/me/library/{a['id']}", json={}, expected=422)
        self.request(
            "PATCH", f"/me/library/{a['id']}", json={"liked": "x" * 3000, "disliked": "x" * 3000}, expected=422
        )
        self.request(
            "PATCH",
            f"/me/library/{a['id']}",
            json={"manual_tags": [{"tag_id": str(self.tags[0]), "value": 1}] * 2},
            expected=422,
        )
        self.request(
            "PATCH",
            f"/me/library/{a['id']}",
            json={"manual_tags": [{"tag_id": str(uuid4()), "value": 1}]},
            expected=422,
        )

    def test_concurrent_updates_and_transaction_rollback(self):
        entry = self.add()

        def update(value):
            with Session(get_engine()) as db:
                return LibraryService(db).update(self.user_id, UUID(entry["id"]), {"rating": value})

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(update, [1, 5]))
        final = self.request("GET", f"/me/library/{entry['id']}")
        weight = self.weights()[self.tags[0]]
        self.assertEqual(
            weight[:2], (Decimal(".3"), Decimal(0)) if final["rating"] == 5 else (Decimal(0), Decimal(".3"))
        )
        before = self.weights()
        with Session(get_engine()) as db:
            with patch("app.db.queries.preferences.PreferencesQueries.rescore", side_effect=RuntimeError("rollback")):
                with self.assertRaises(RuntimeError):
                    LibraryService(db).update(self.user_id, UUID(entry["id"]), {"rating": 4})
        self.assertEqual(self.weights(), before)

    def test_database_constraints_and_generated_coefficient(self):
        with Session(get_engine()) as db:
            db.add(Library(user_id=self.user_id, status="planned"))
            with self.assertRaises(IntegrityError):
                db.commit()
        feedback = self.mark_tags([{"tag_id": str(self.tags[0]), "value": 1}])
        self.assertAlmostEqual(float(self.weights()[self.tags[0]][2]), 1 / 3)
        entry = self.add(manual_tags=[{"tag_id": str(self.tags[0]), "value": -1}])
        self.assertEqual(self.weights()[self.tags[0]][2], Decimal(0))
        self.request("DELETE", f"/me/library/{feedback['id']}", expected=204)
        self.assertAlmostEqual(float(self.weights()[self.tags[0]][2]), -1 / 3)
        self.update(entry, manual_tags=[])
        self.assertEqual(self.weights(), {})

    def test_profile_preferences_are_not_exposed(self):
        self.request("GET", "/me/preferences", expected=404)
        self.request("PUT", "/me/preferences", expected=404, json={"choices": []})

    def test_model_output_validation(self):
        tags = [{"id": str(self.tags[0]), "name": "Тег"}]
        texts = {"liked": "Мне нравится герой", "disliked": None, "comment": None}
        signal = {"tag_id": str(self.tags[0]), "value": 1, "quote": "нравится герой"}
        valid = json.dumps({"signals": [signal]})
        self.assertEqual(len(ReviewModel.validate(valid, texts, tags)), 1)
        invalid = [
            "```json\n" + valid + "\n```",
            json.dumps({"signals": [signal, signal]}),
            json.dumps({"signals": [{**signal, "quote": "выдуманная цитата"}]}),
            json.dumps({"signals": [{**signal, "value": True}]}),
            json.dumps({"signals": [{**signal, "tag_id": str(uuid4())}]}),
            json.dumps({"signals": [], "extra": 1}),
        ]
        for content in invalid:
            with self.assertRaises(ValueError):
                ReviewModel.validate(content, texts, tags)

    def test_unicode_search_and_optional_nulls(self):
        self.assertEqual(self.request("GET", "/works?q=АЛЬФА")["total"], 1)
        self.assertEqual(self.request("GET", "/works?q=альфа")["total"], 1)
        entry = self.request(
            "POST",
            "/me/private-works",
            expected=201,
            json={
                "title": "КНИГА",
                "type": "other",
                "description": None,
                "author": "   ",
                "country": None,
                "entry": {"liked": "  ", "disliked": None, "comment": None},
            },
        )
        self.assertEqual(self.request("GET", "/me/library?q=книга")["total"], 1)
        self.assertEqual(entry["analysis"]["status"], "none")
        self.request("PATCH", f"/me/private-works/{entry['work']['id']}", json={"title": None}, expected=422)

    def test_zero_scores_negative_general_and_mathematical_scores(self):
        feedback = self.mark_tags([{ "tag_id": str(self.tags[0]), "value": 1}, {"tag_id": str(self.tags[1]), "value": -1}])
        from app.db.models import Recommendation

        with Session(get_engine()) as db:
            alpha = db.get(Recommendation, (self.user_id, self.works[0]))
            beta = db.get(Recommendation, (self.user_id, self.works[1]))
            self.assertEqual(alpha.score, 0)
            self.assertAlmostEqual(float(beta.score), 1 / 3)
        self.update(feedback, manual_tags=[{"tag_id": str(self.tags[0]), "value": -1}])
        result = self.request("GET", "/me/recommendations")
        self.assertEqual(result["mode"], "general")
        self.assertEqual({r["work"]["id"] for r in result["items"][-2:]}, {str(self.works[0]), str(self.works[1])})

    def test_deleted_review_result_cannot_restore_contributions(self):
        entry = self.add(liked="Герой")
        with Session(get_engine()) as db:
            job = AnalysisService(db).claim()
        self.request("DELETE", f"/me/library/{entry['id']}", expected=204)
        with Session(get_engine()) as db:
            self.assertFalse(
                AnalysisService(db).apply(
                    job, [{"tag_id": self.tags[0], "value": 1, "source": "review", "quote": "Герой"}]
                )
            )
        self.assertEqual(self.weights(), {})

    def test_catalog_update_replaces_only_rating_contributions(self):
        from tempfile import TemporaryDirectory

        from app.db.seed import import_catalog

        self.add(3, rating=5)
        self.add(0, manual_tags=[{"tag_id": str(self.tags[2]), "value": -1}])
        catalog = {
            "works": [
                {
                    "id": str(self.works[3]),
                    "title": "Дельта 100%_",
                    "type": "book",
                    "genres": [],
                    "tag_ids": [str(self.tags[0])],
                }
            ]
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "works.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with Session(get_engine()) as db:
                import_catalog(db, path)
                db.commit()
            self.assertEqual(self.weights()[self.tags[0]][0], Decimal(".3"))
            self.assertEqual(self.weights()[self.tags[2]][1], Decimal(1))
            before = self.weights()
            with Session(get_engine()) as db:
                with patch(
                    "app.db.queries.preferences.PreferencesQueries.rescore",
                    side_effect=AssertionError("Лишний пересчёт"),
                ):
                    import_catalog(db, path)
                    db.commit()
            self.assertEqual(self.weights(), before)
            catalog["works"][0]["tag_ids"] = []
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with Session(get_engine()) as db:
                import_catalog(db, path)
                db.commit()
            self.assertNotIn(self.tags[0], self.weights())

    def test_cover_errors_and_private_owner_constraint(self):
        entry = self.request("POST", "/me/private-works", expected=201, json={"title": "Своя", "type": "book"})
        path = f"/me/private-works/{entry['work']['id']}/cover"
        self.request("PUT", path, files={"file": ("x.txt", b"not image", "text/plain")}, expected=415)
        self.request("PUT", path, files={"file": ("x.png", b"x" * (10_485_760 + 1), "image/png")}, expected=413)
        image = io.BytesIO()
        Image.new("RGB", (8001, 1)).save(image, "PNG")
        self.request("PUT", path, files={"file": ("x.png", image.getvalue(), "image/png")}, expected=422)
        with Session(get_engine()) as db:
            # убираем дубль для проверки владельца
            original = db.get(Library, UUID(entry["id"]))
            db.delete(original)
            db.flush()
            db.add(Library(user_id=self.other_id, private_id=UUID(entry["work"]["id"]), status="planned"))
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_code_expiry_resend_and_existing_account(self):
        codes = []
        with patch("app.services.auth.send_code", side_effect=lambda email, code: codes.append(code)):
            first = self.request("POST", "/auth/request-code", json={"email": "first@example.com"})
            with Session(get_engine()) as db:
                row = db.get(Code, UUID(first["code_id"]))
                row.created_at -= timedelta(minutes=11)
                row.expires_at -= timedelta(minutes=11)
                db.commit()
            self.request(
                "POST", "/auth/verify-code", json={"code_id": first["code_id"], "code": codes[0]}, expected=410
            )
            second = self.request("POST", "/auth/request-code", json={"email": "first@example.com"})
            self.request(
                "POST", "/auth/verify-code", json={"code_id": first["code_id"], "code": codes[0]}, expected=422
            )
            login = self.request("POST", "/auth/verify-code", json={"code_id": second["code_id"], "code": codes[1]})
            self.assertFalse(login["is_new_user"])
            self.assertEqual(login["user"]["id"], str(self.user_id))

    def test_email_over_local_smtp(self):
        import email
        import re
        import socketserver
        import threading
        from email import policy

        messages = []

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.wfile.write(b"220 localhost SMTP\r\n")
                while line := self.rfile.readline():
                    command = line.split(b" ", 1)[0].strip().upper()
                    if command == b"DATA":
                        self.wfile.write(b"354 Send message\r\n")
                        lines = []
                        while (line := self.rfile.readline()) not in (b".\r\n", b""):
                            lines.append(line)
                        messages.append(email.message_from_bytes(b"".join(lines), policy=policy.default))
                        self.wfile.write(b"250 Accepted\r\n")
                    elif command == b"QUIT":
                        self.wfile.write(b"221 Bye\r\n")
                        return
                    else:
                        self.wfile.write(b"250 OK\r\n")

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            settings = get_settings().model_copy(
                update={
                    "smtp_host": "127.0.0.1",
                    "smtp_port": server.server_address[1],
                    "smtp_from": "sender@example.com",
                    "smtp_user": "",
                    "smtp_tls": False,
                    "smtp_ssl": False,
                }
            )
            try:
                with patch("app.core.mail.get_settings", return_value=settings):
                    issued = self.request("POST", "/auth/request-code", json={"email": "mail@example.com"})
                self.assertEqual(messages[0]["To"], "mail@example.com")
                code = re.search(r"\b[0-9]{6}\b", messages[0].get_content()).group()
                self.request("POST", "/auth/verify-code", json={"code_id": issued["code_id"], "code": code})
            finally:
                server.shutdown()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
