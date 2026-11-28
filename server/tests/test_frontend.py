import io
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.recommendations import catalog_maps
from app.core.reference import TYPE_IDS
from app.core.security import create_token
from app.db.models import Library, LibraryTag, Recommendation, Tag, UserTag, Work, WorkGenre, WorkTag
from app.db.queries.preferences import PreferencesQueries
from app.db.session import get_engine
from app.main import app
from app.services.analysis import AnalysisService
from app.services.covers import CoversService
from tests.test_api import ORIGIN, ApiFixture


class FrontendTests(ApiFixture):
    def private(self, **values):
        return self.request(
            "POST", "/me/private-works", expected=201, json={"title": "Личная книга", "type": "book", **values}
        )

    def assert_consistent(self):
        # сверяем суммы и баллы отдельным расчётом
        with Session(get_engine()) as db:
            signals = db.execute(
                select(LibraryTag.tag_id, LibraryTag.value).join(Library).where(Library.user_id == self.user_id)
            ).all()
            rows = {r.tag_id: r for r in db.scalars(select(UserTag).where(UserTag.user_id == self.user_id))}
            totals = {}
            for tag, value in signals:
                positive, negative = totals.get(tag, (Decimal(0), Decimal(0)))
                totals[tag] = (positive + max(value, 0), negative + max(-value, 0))
            for tag in totals.keys() | rows.keys():
                positive, negative = totals.get(tag, (Decimal(0), Decimal(0)))
                row = rows.get(tag)
                if positive or negative:
                    self.assertIsNotNone(row)
                if row:
                    self.assertEqual((row.positive, row.negative), (positive, negative))
                    expected = (positive - negative) / (2 + positive + negative)
                    self.assertAlmostEqual(float(row.weight), float(expected), places=12)
            tag_map, main_map, genre_map = catalog_maps(
                db.execute(select(WorkTag.work_id, WorkTag.tag_id, WorkTag.is_main)),
                db.execute(select(WorkGenre.work_id, WorkGenre.genre_id)),
            )
            profile, ratings = PreferencesQueries(db).context(self.user_id, genre_map)
            scorer = PreferencesQueries(db).scorer(self.user_id)
            stored = dict(
                db.execute(
                    select(Recommendation.work_id, Recommendation.score).where(Recommendation.user_id == self.user_id)
                ).all()
            )
            for work in db.scalars(select(Work)):
                expected = scorer.score(work.id, profile, ratings)
                self.assertAlmostEqual(float(stored.get(work.id, 0)), float(expected), places=12)

    def test_report_screen_journey(self):
        with Session(get_engine()) as db:
            for work_id, title in zip(
                self.works, ["Dungeon Meshi", "To be hero X", "Цирцея", "Link Click", "Sousou no Frieren"]
            ):
                work = db.get(Work, work_id)
                work.title = title
                work.description = "Описание произведения"
                work.author = "Создатель"
                work.country = "Страна"
            db.commit()
        types = self.request("GET", "/types")["items"]
        codes = {row["code"] for row in types}
        for row in types:
            self.assertEqual(set(row), {"code", "name"})
        catalog = self.request("GET", "/works")["items"]
        for card in catalog:
            self.assertIn(card["type"], codes)
            for field in ("cover_url", "title", "type", "year", "genres", "library"):
                self.assertIn(field, card)
        manga = self.add(0, status="in_progress")
        anime = self.add(
            1, status="completed", rating=5, liked="Всё круто классно", disliked="-", comment="Второй сезон где"
        )
        self.assertEqual(self.request("GET", "/me/library")["total"], 2)
        detail = self.request("GET", f"/works/{self.works[1]}")
        self.assertEqual(detail["entry"]["id"], anime["id"])
        self.assertEqual(detail["entry"]["liked"], "Всё круто классно")
        for field in ("country", "author", "description", "genres"):
            self.assertIn(field, detail["work"])
        with Session(get_engine()) as db:
            job = AnalysisService(db).claim()
        with Session(get_engine()) as db:
            AnalysisService(db).apply(job, [])
        analyzed = self.request("GET", f"/me/library/{anime['id']}/analysis")
        self.assertEqual(analyzed["effective_source"], "rating")
        recommendations = self.request("GET", "/me/recommendations")
        for item in recommendations["items"]:
            self.assertTrue(item["reason"]["text"])
            source = item["reason"]["source_work"]
            if source:
                self.request("GET", f"/works/{source['id']}")
            self.assertNotIn(item["work"]["id"], [manga["work"]["id"], anime["work"]["id"]])
        self.request("GET", f"/works/{self.works[1]}/similar")
        self.update(
            anime, liked=None, disliked=None, comment=None, manual_tags=[{"tag_id": str(self.tags[2]), "value": 1}]
        )
        detail = self.request("GET", f"/works/{self.works[1]}")
        self.assertEqual(detail["entry"]["effective_source"], "manual")
        self.assert_consistent()

    def test_invalid_scalar_values_never_return_500(self):
        cases = [None, [], {}, True, False, -1, 0, 1.2, "", " ", "5", float("nan"), float("inf")]
        for value in cases:
            with self.subTest(value=repr(value)):
                raw = json.dumps({"title": "Книга", "type": "book", "entry": {"rating": value}})
                expected = 201 if value is None else 422
                self.request(
                    "POST",
                    "/me/private-works",
                    expected=expected,
                    content=raw,
                    headers={"Content-Type": "application/json"},
                )

    def test_malformed_json_returns_validation_error(self):
        payloads = [
            b"{",
            b'{"title":"x","type":"book","\\ud800":1}',
            b'{"title":"x","type":"book","extra":' + b"[" * 1500 + b"0" + b"]" * 1500 + b"}",
            b"null",
            b"[]",
            b'"text"',
        ]
        for raw in payloads:
            with self.subTest(payload=raw[:60]):
                self.request(
                    "POST", "/me/private-works", expected=422, content=raw, headers={"Content-Type": "application/json"}
                )

    def test_postgres_invalid_text_is_validation_error(self):
        for key, value in [("title", "abc\0def"), ("description", "abc\0def"), ("country", "\0"), ("author", "\ud800")]:
            with self.subTest(key=key):
                raw = json.dumps({"title": "Книга", "type": "book", key: value})
                self.request(
                    "POST", "/me/private-works", expected=422, content=raw, headers={"Content-Type": "application/json"}
                )
        self.request("GET", "/works?q=%00", expected=422)
        self.request("PATCH", "/me", json={"name": "x\0y"}, expected=422)

    def test_arbitrarily_large_offset_is_empty_page(self):
        for path in [
            "/works",
            "/me/library",
            "/me/hidden",
            "/me/recommendations",
            "/tags",
            f"/works/{self.works[0]}/similar",
        ]:
            with self.subTest(path=path):
                result = self.request("GET", path + "?offset=999999999999999999999999999999")
                self.assertEqual(result["items"], [])

    def test_whitespace_limits_and_all_types(self):
        for work_type in TYPE_IDS:
            entry = self.private(type=work_type)
            self.assertEqual(entry["work"]["type"], work_type)
        entry = self.private(title="К" * 300, description="Д" * 10000, author="А" * 1000, country="С" * 100, year=9999)
        self.assertEqual(len(entry["work"]["title"]), 300)
        for key, value in [
            ("title", "К" * 301),
            ("description", "Д" * 10001),
            ("author", "А" * 1001),
            ("country", "С" * 101),
            ("year", 10000),
        ]:
            self.request("POST", "/me/private-works", expected=422, json={"title": "Книга", "type": "book", key: value})
        self.update(entry, liked="я" * 2500, disliked="ю" * 2500)
        self.request("PATCH", f"/me/library/{entry['id']}", json={"comment": "!"}, expected=422)
        entry = self.update(entry, liked="   ", disliked="\n\t", comment=None)
        self.assertEqual(entry["analysis"]["status"], "none")

    def test_duplicate_and_unknown_arrays_are_atomic(self):
        entry = self.add(rating=5)
        before = self.weights()
        bad = [[{"tag_id": str(self.tags[0]), "value": 1}] * 2, [{"tag_id": str(uuid4()), "value": 1}]]
        for tags in bad:
            self.request("PATCH", f"/me/library/{entry['id']}", expected=422, json={"rating": 1, "manual_tags": tags})
            self.assertEqual(self.weights(), before)
            self.assertEqual(self.request("GET", f"/me/library/{entry['id']}")["rating"], 5)
        with Session(get_engine()) as db:
            tags = list(db.scalars(select(Tag.id).order_by(Tag.id).limit(101)))
        self.update(entry, manual_tags=[{"tag_id": str(t), "value": 1} for t in tags[:100]])
        self.request(
            "PATCH", f"/me/library/{entry['id']}", expected=422,
            json={"manual_tags": [{"tag_id": str(t), "value": 1} for t in tags]},
        )
        self.assertEqual(len(self.request("GET", f"/me/library/{entry['id']}")["signals"]), 100)
        self.assert_consistent()

    def test_double_click_add_and_parallel_updates(self):
        def add():
            with TestClient(app, headers={"Origin": ORIGIN}) as client:
                client.cookies.set("access_token", create_token(self.user_id))
                response = client.post("/api/v1/me/library", json={"work_id": str(self.works[0]), "rating": 5})
                return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _: add(), range(6)))
        self.assertEqual(sorted(code for code, _ in results), [201, 409, 409, 409, 409, 409])
        entry = next(body for code, body in results if code == 201)

        def change(value):
            with TestClient(app, headers={"Origin": ORIGIN}) as client:
                client.cookies.set("access_token", create_token(self.user_id))
                return client.patch("/api/v1/me/library/" + entry["id"], json={"rating": value}).status_code

        with ThreadPoolExecutor(max_workers=6) as executor:
            self.assertEqual(list(executor.map(change, [1, 5, 2, 4, 3, 5])), [200] * 6)
        self.assert_consistent()

    def test_random_user_actions_keep_exact_coefficients(self):
        rng = random.Random(20261126)
        entries = [self.add(i) for i in range(5)]
        for step in range(70):
            entry = rng.choice(entries)
            action = rng.randrange(3)
            if action == 0:
                self.update(entry, rating=rng.choice([None, 1, 2, 3, 4, 5]))
            elif action == 1:
                selected = rng.sample(self.tags, rng.randrange(4))
                self.update(entry, manual_tags=[{"tag_id": str(t), "value": rng.choice([-1, 1])} for t in selected])
            elif action == 2:
                self.update(entry, status=rng.choice(["planned", "in_progress", "completed", "dropped"]))
            with self.subTest(step=step):
                self.assert_consistent()
        for entry in entries:
            self.request("DELETE", f"/me/library/{entry['id']}", expected=204)
            self.assert_consistent()

    def test_foreign_writes_and_cover_access_are_denied(self):
        entry = self.private()
        work_id = entry["work"]["id"]
        self.client.cookies.set("access_token", create_token(self.other_id))
        for method, path, kwargs in [
            ("PATCH", f"/me/library/{entry['id']}", {"json": {"rating": 1}}),
            ("DELETE", f"/me/library/{entry['id']}", {}),
            ("POST", f"/me/library/{entry['id']}/analysis/retry", {}),
            ("PATCH", f"/me/private-works/{work_id}", {"json": {"title": "Подмена"}}),
            ("PUT", f"/me/private-works/{work_id}/cover", {"files": {"file": ("x", b"x", "image/png")}}),
            ("DELETE", f"/me/private-works/{work_id}/cover", {}),
        ]:
            self.request(method, path, expected=404, **kwargs)
        self.client.cookies.set("access_token", create_token(self.user_id))
        self.assertEqual(self.request("GET", f"/me/private-works/{work_id}")["work"]["title"], "Личная книга")

    def test_jwt_and_origin_edge_cases(self):
        now = datetime.now(timezone.utc)
        key = get_settings().jwt_secret.get_secret_value()
        tokens = [
            "garbage",
            jwt.encode(
                {"sub": str(self.user_id), "type": "access", "iat": now, "exp": now - timedelta(seconds=1)}, key, algorithm="HS256"
            ),
            jwt.encode(
                {"sub": str(self.user_id), "type": "access", "iat": now, "exp": now + timedelta(hours=1)}, "x" * 40, algorithm="HS256"
            ),
            jwt.encode({"sub": str(uuid4()), "type": "access", "iat": now, "exp": now + timedelta(hours=1)}, key, algorithm="HS256"),
        ]
        for token in tokens:
            self.client.cookies.set("access_token", token)
            self.request("GET", "/me", expected=401)
        self.client.cookies.set("access_token", create_token(self.user_id))
        for origin in ["", "null", ORIGIN + ".evil.test", ORIGIN + "/", "http://127.0.0.1:8001"]:
            self.request("POST", "/auth/logout", headers={"Origin": origin}, expected=403)

    def test_filter_combinations_and_page_partitions(self):
        for query in [
            "",
            "?types=book",
            f"?genre_ids={self.genre}",
            f"?tag_ids={self.tags[0]}",
            f"?exclude_tag_ids={self.tags[1]}",
            "?q=а",
            "?sort=year_desc",
        ]:
            full = self.request("GET", "/works" + query)
            pages = []
            for offset in range(full["total"] + 1):
                suffix = ("&" if query else "?") + f"limit=1&offset={offset}"
                page = self.request("GET", "/works" + query + suffix)
                self.assertEqual(page["total"], full["total"])
                pages.extend(page["items"])
            self.assertEqual([i["id"] for i in pages], [i["id"] for i in full["items"]])
        self.request("GET", "/works?q=%27%20OR%201%3D1--")
        self.assertEqual(self.request("GET", "/works?q=%25")["total"], 1)

    def test_cover_deleted_during_get_is_not_500(self):
        entry = self.private()
        image = io.BytesIO()
        Image.new("RGB", (20, 20)).save(image, "PNG")
        path = f"/me/private-works/{entry['work']['id']}/cover"
        self.request("PUT", path, files={"file": ("x.png", image.getvalue(), "image/png")})

        class VanishingPath:
            def is_file(self):
                return True

            def __fspath__(self):
                return str(Path(get_settings().storage_dir) / "does-not-exist.webp")

            def read_bytes(self):
                raise FileNotFoundError()

        with patch.object(CoversService, "path", return_value=VanishingPath()):
            self.request("GET", path, expected=404)

    def test_file_variants_and_failed_replace_preserve_old_cover(self):
        entry = self.private()
        path = f"/me/private-works/{entry['work']['id']}/cover"
        for format, mime in [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]:
            image = io.BytesIO()
            Image.new("RGB", (20, 30)).save(image, format)
            self.request("PUT", path, files={"file": ("../../escape", image.getvalue(), mime)})
            result = self.client.get("/api/v1" + path)
            self.assertEqual(result.status_code, 200)
        before = self.client.get("/api/v1" + path).content
        self.request("PUT", path, files={"file": ("broken.png", b"\x89PNG\r\n\x1a\n", "image/png")}, expected=422)
        self.assertEqual(self.client.get("/api/v1" + path).content, before)

        animated = io.BytesIO()
        Image.new("RGB", (20, 30), "red").save(
            animated, "PNG", save_all=True, append_images=[Image.new("RGB", (20, 30), "blue")], duration=50, loop=0
        )
        self.request("PUT", path, files={"file": ("animated.png", animated.getvalue(), "image/png")}, expected=422)
        self.request(
            "PUT",
            path,
            files=[("file", ("1.png", before, "image/webp")), ("file", ("2.png", before, "image/webp"))],
            expected=422,
        )
        with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("DB unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.put("/api/v1" + path, files={"file": ("new.webp", before, "image/webp")})
        self.assertEqual(self.client.get("/api/v1" + path).content, before)

    def test_http_journey_with_cookie_login_all_routes(self):
        catalog = patch("app.services.covers.CATALOG_DIR", get_settings().storage_dir / "catalog")
        catalog.start()
        self.addCleanup(catalog.stop)
        import socket
        import threading
        import time

        import httpx
        import uvicorn

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        sent = []
        routes = set()

        def call(client, method, path, status=200, **kwargs):
            response = client.request(method, path, **kwargs)
            self.assertEqual(response.status_code, status, response.text[:500])
            normalized = path.split("?")[0]
            for value in normalized.split("/"):
                try:
                    UUID(value)
                except ValueError:
                    continue
                normalized = normalized.replace(value, "{work_id}" if "/hidden/" in path else "{id}")
            routes.add((method, normalized))
            return response

        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            self.assertTrue(server.started)
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}/api/v1/", headers={"Origin": ORIGIN}, timeout=15
            ) as client:
                call(client, "GET", "me", 401)
                with patch("app.services.auth.send_code", side_effect=lambda email, code: sent.append(code)):
                    issued = call(client, "POST", "auth/request-code", json={"email": "browser@example.com"}).json()
                login = call(client, "POST", "auth/verify-code", json={"code_id": issued["code_id"], "code": sent[0]})
                self.assertIn("HttpOnly", login.headers["set-cookie"])
                call(client, "GET", "me")
                call(client, "PATCH", "me", json={"name": "Читатель"})
                call(client, "GET", "types")
                call(client, "GET", "genres")
                call(client, "GET", "tags")
                catalog = call(client, "GET", "works").json()
                work_id = catalog["items"][0]["id"]
                call(client, "GET", f"works/{work_id}")
                cover = io.BytesIO()
                Image.new("RGB", (20, 30)).save(cover, "WEBP")
                cover_path = CoversService.path("catalog/http-smoke.webp")
                cover_path.parent.mkdir(parents=True, exist_ok=True)
                cover_path.write_bytes(cover.getvalue())
                with Session(get_engine()) as db:
                    work = db.get(Work, UUID(work_id))
                    work.cover = "catalog/http-smoke.webp"
                    db.commit()
                call(client, "GET", f"works/{work_id}/cover")
                entry = call(client, "POST", "me/library", 201, json={"work_id": work_id}).json()
                eid = entry["id"]
                call(client, "GET", "me/library")
                call(client, "GET", f"me/library/{eid}")
                call(client, "PATCH", f"me/library/{eid}", json={"liked": "Мне понравился герой", "rating": 5})
                call(client, "GET", f"me/library/{eid}/analysis")
                with Session(get_engine()) as db:
                    job = AnalysisService(db).claim()
                with Session(get_engine()) as db:
                    AnalysisService(db).apply(job, error=True)
                call(client, "POST", f"me/library/{eid}/analysis/retry", 202)
                with Session(get_engine()) as db:
                    job = AnalysisService(db).claim()
                with Session(get_engine()) as db:
                    AnalysisService(db).apply(job, [])
                private = call(
                    client, "POST", "me/private-works", 201, json={"title": "Своя книга", "type": "book"}
                ).json()
                pid = private["work"]["id"]
                call(client, "GET", f"me/private-works/{pid}")
                call(client, "PATCH", f"me/private-works/{pid}", json={"genre_ids": [str(self.genre)]})
                call(
                    client,
                    "PUT",
                    f"me/private-works/{pid}/cover",
                    files={"file": ("cover.webp", cover.getvalue(), "image/webp")},
                )
                call(client, "GET", f"me/private-works/{pid}/cover")
                call(client, "GET", "me/recommendations")
                call(client, "GET", f"works/{work_id}/similar")
                call(client, "GET", f"me/private-works/{pid}/similar")
                hide_id = str(self.works[-1])
                call(client, "PUT", f"me/hidden/{hide_id}", 204)
                call(client, "GET", "me/hidden")
                call(client, "DELETE", f"me/hidden/{hide_id}", 204)
                call(client, "DELETE", f"me/private-works/{pid}/cover", 204)
                call(client, "DELETE", f"me/library/{private['id']}", 204)
                call(client, "DELETE", f"me/library/{eid}", 204)
                call(client, "POST", "auth/refresh", 204)
                call(client, "POST", "auth/logout", 204)
                call(client, "GET", "me", 401)
            self.assertEqual(len(routes), 31)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
