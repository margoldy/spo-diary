import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.recommendations import ContentScores, catalog_maps
from app.db.models import Recommendation
from app.db.seed import import_catalog
from app.db.session import get_engine
from tests.evaluate_recommendations import verify_quality
from tests.test_api import ApiFixture

CATALOG = Path(__file__).resolve().parents[1] / "data/works.json"


class RecommendationsTests(ApiFixture):
    def setUp(self):
        super().setUp()
        self.catalog = json.loads(CATALOG.read_text("utf-8"))
        self.titles = self.catalog["works"]
        with Session(get_engine()) as db:
            self.assertEqual(db.bind.url.database, "spo_diary_test")
            db.execute(text("TRUNCATE works, work_groups CASCADE"))
            import_catalog(db, CATALOG)
            db.commit()

    def rate(self, index, rating=5):
        return self.request(
            "POST", "/me/library", expected=201, json={"work_id": self.titles[index]["id"], "rating": rating}
        )

    def recommendations(self):
        return self.request("GET", "/me/recommendations?limit=100")

    def test_rated_action_does_not_recommend_unrelated_family_fantasy(self):
        self.rate(200)
        response = self.recommendations()
        ids = [item["work"]["id"] for item in response["items"]]
        for index in (24, 27, 200):
            self.assertNotIn(self.titles[index]["id"], ids)
        for index in (159, 107, 158):
            self.assertIn(self.titles[index]["id"], ids[:5])
        self.assertTrue(
            all(item["reason"]["source_work"]["id"] == self.titles[200]["id"] for item in response["items"])
        )

    def test_music_sports_and_time_rating_scenarios(self):
        for source, expected in [(52, {118, 79, 28}), (5, {85, 126, 89}), (73, {43, 95, 50})]:
            with self.subTest(source=source):
                entry = self.rate(source)
                top = {item["work"]["id"] for item in self.recommendations()["items"][:5]}
                self.assertTrue({self.titles[i]["id"] for i in expected}.issubset(top))
                self.request("DELETE", f"/me/library/{entry['id']}", expected=204)

    def test_explicit_preference_is_not_a_title_blacklist(self):
        self.rate(200)
        tag = self.catalog["tags"][97]["id"]
        feedback = self.mark_tags([{"tag_id": tag, "value": 1}])
        item = next(item for item in self.recommendations()["items"] if item["work"]["id"] == self.titles[24]["id"])
        self.assertEqual(item["reason"]["source_work"]["id"], feedback["work"]["id"])
        self.assertIn("Уютная атмосфера", item["reason"]["text"])

    def test_rating_replacement_and_deletion_remove_saved_effect(self):
        entry = self.rate(200)
        target = UUID(self.titles[159]["id"])
        with Session(get_engine()) as db:
            self.assertGreater(db.get(Recommendation, (self.user_id, target)).score, 0)
        self.update(entry, rating=1)
        with Session(get_engine()) as db:
            self.assertLess(db.get(Recommendation, (self.user_id, target)).score, 0)
        self.request("DELETE", f"/me/library/{entry['id']}", expected=204)
        with Session(get_engine()) as db:
            self.assertEqual(list(db.scalars(select(Recommendation).where(Recommendation.user_id == self.user_id))), [])

    def test_score_is_content_based_and_explicit_dislike_wins(self):
        tags, main, genres = catalog_maps(
            [("a", "x", True), ("a", "background", False), ("b", "x", True), ("c", "background", True)],
            [("a", "fantasy"), ("b", "fantasy"), ("c", "fantasy")],
        )
        scorer = ContentScores(tags, main, genres)
        ratings = [dict(tag_id="x", value=Decimal(".3"), work_id="a", library_id="entry")]
        profile = {"x": (Decimal(".3"), 0)}
        self.assertAlmostEqual(float(scorer.score("b", profile, ratings)), 0.3 / 2.3)
        self.assertEqual(scorer.score("c", profile, ratings), 0)
        profile["x"] = (Decimal(".3"), 1)
        self.assertAlmostEqual(float(scorer.score("b", profile, ratings)), -1 / 3)
        genres["b"] = {"sport"}
        profile["x"] = (Decimal(".3"), 0)
        self.assertEqual(scorer.score("b", profile, ratings), 0)

    def test_genre_only_import_rebuilds_scores_without_changing_user_weights(self):
        self.rate(200)
        target = UUID(self.titles[159]["id"])
        previous = self.weights()
        with Session(get_engine()) as db:
            self.assertGreater(db.get(Recommendation, (self.user_id, target)).score, 0)
        # меняем только жанры кандидата
        row = dict(self.titles[159], genres=["Спорт"], cover=None)
        path = Path(__file__).resolve().parents[1] / ".local/genre-import-check.json"
        path.write_text(json.dumps({"works": [row]}), encoding="utf-8")
        with Session(get_engine()) as db:
            import_catalog(db, path)
            db.commit()
        self.assertEqual(self.weights(), previous)
        with Session(get_engine()) as db:
            self.assertEqual(db.get(Recommendation, (self.user_id, target)).score, 0)
        self.assertNotIn(str(target), {r["work"]["id"] for r in self.recommendations()["items"]})

    def test_quality_comparison_uses_frozen_content_annotations(self):
        self.assertEqual(len(verify_quality(self.catalog)), 23)

    def test_creative_rating_stays_about_creativity(self):
        entry = self.rate(101)
        self.assertIn(self.catalog["tags"][41]["id"], {signal["tag"]["id"] for signal in entry["signals"]})
        top = {item["work"]["id"] for item in self.recommendations()["items"][:5]}
        self.assertTrue({self.titles[index]["id"] for index in (78, 90, 68, 118)}.issubset(top))

    def test_explicit_family_interest_does_not_depend_on_nature_rating(self):
        self.rate(48)
        tag = self.catalog["tags"][19]["id"]
        self.mark_tags([{"tag_id": tag, "value": 1}])
        top = {item["work"]["id"] for item in self.recommendations()["items"][:5]}
        self.assertTrue({self.titles[i]["id"] for i in (91, 120, 152)}.issubset(top))

    def test_rare_genre_distinguishes_music_from_general_comedy(self):
        tags, main, genres = catalog_maps(
            [(work, "friendship", True) for work in ("source", "music", "comedy", "extra")],
            [("source", "music"), ("source", "comedy"), ("music", "music"), ("comedy", "comedy"), ("extra", "comedy")],
        )
        scores = ContentScores(tags, main, genres)
        self.assertGreater(scores.similarity("source", "music"), scores.similarity("source", "comedy"))

    def test_unknown_genres_and_empty_tags_are_supported(self):
        tags, main, genres = catalog_maps([("source", "x", True), ("target", "x", True)], [])
        scores = ContentScores(tags, main, genres)
        self.assertEqual(scores.similarity("source", "target"), 1)
        self.assertEqual(scores.similarity("source", "empty"), 0)
        self.assertEqual(scores.score("empty", {"x": (1, 0)}, []), 0)

        genres["source"], genres["target"] = {"music"}, {"comedy"}
        before = ContentScores(tags, main, genres).genre_idf
        genres["unknown"] = set()
        self.assertEqual(ContentScores(tags, main, genres).genre_idf, before)

    def test_background_interest_has_reason_and_dislike_is_not_weakened(self):
        tag_id = self.catalog["tags"][57]["id"]
        target = UUID(self.titles[40]["id"])
        feedback = self.mark_tags([{"tag_id": tag_id, "value": 1}])
        item = next(item for item in self.recommendations()["items"] if item["work"]["id"] == str(target))
        self.assertIn("Творчество и создание произведений", item["reason"]["text"])
        self.assertEqual(item["reason"]["source_work"]["id"], feedback["work"]["id"])
        with Session(get_engine()) as db:
            positive = db.get(Recommendation, (self.user_id, target)).score
        self.update(feedback, manual_tags=[{"tag_id": tag_id, "value": -1}])
        with Session(get_engine()) as db:
            negative = db.get(Recommendation, (self.user_id, target)).score
        self.assertGreater(positive, 0)
        self.assertAlmostEqual(float(negative), float(-4 * positive))
