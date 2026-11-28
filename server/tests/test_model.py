import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from uuid import UUID

import httpx
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.model import MAX_SIGNALS, Observations, ReviewModel, general_reaction


class ModelTests(unittest.TestCase):
    tags = [{"id": str(UUID(int=2)), "name": "Тег Б"}, {"id": str(UUID(int=1)), "name": "Тег А"}]

    def test_cache_session_shares_only_the_constant_prefix(self):
        messages, _, _ = ReviewModel.prepare({"liked": "Первый личный отзыв"}, self.tags)
        payload = {
            "model": "gpt://folder/qwen3.6-35b-a3b/latest",
            "messages": messages,
            "response_format": Observations.model_json_schema(),
        }
        key = ReviewModel.cache_session(payload)
        other = deepcopy(payload)
        other["messages"], _, _ = ReviewModel.prepare({"disliked": "Другой отзыв"}, self.tags[::-1])
        other["max_tokens"] = 800
        self.assertEqual(ReviewModel.cache_session(other), key)
        self.assertEqual(ReviewModel().cache_session(other), key)
        self.assertRegex(key, r"^[a-f0-9]{64}$")
        for change in ("model", "system", "tags", "schema"):
            other = deepcopy(payload)
            if change == "model":
                other["model"] += "-changed"
            elif change == "system":
                other["messages"][0]["content"] += " Новая инструкция"
            elif change == "tags":
                tags = [{**row, "name": row["name"] + " новый"} for row in self.tags]
                other["messages"], _, _ = ReviewModel.prepare({"liked": "Отзыв"}, tags)
            else:
                other["response_format"]["title"] = "ChangedSchema"
            with self.subTest(change=change):
                self.assertNotEqual(ReviewModel.cache_session(other), key)

    def test_evidence_and_tag_mapping(self):
        texts = {"liked": "  Нравится! Да.\r\nЕщё. ", "disliked": None, "comment": "Не нравится? Нет."}
        messages, tags, evidence = ReviewModel.prepare(texts, self.tags)
        self.assertEqual([row["name"] for row in tags], ["Тег А", "Тег Б"])
        self.assertEqual(len(evidence), 5)
        for item in evidence:
            self.assertIn(item["text"], texts[item["field"]])
        self.assertNotIn(self.tags[0]["id"], str(messages))
        content = json.dumps({"observations": [{"tag": 2, "evidence": 4, "sentiment": "negative"}]})
        rows = ReviewModel.normalize(content, texts, tags, evidence)
        self.assertEqual(rows, [{"tag_id": UUID(int=2), "value": -1, "quote": "Не нравится?", "source": "review"}])

    def test_mixed_and_repeated_observations_count_once(self):
        texts = {"liked": "Тег А понравился.", "disliked": "Тег А раздражает."}
        _, tags, evidence = ReviewModel.prepare(texts, self.tags)
        positive = {"tag": 1, "evidence": 1, "sentiment": "positive"}
        negative = {"tag": 1, "evidence": 2, "sentiment": "negative"}
        for observations, expected in [
            ([positive, positive], 1),
            ([{**positive, "sentiment": "mixed"}], 0),
            ([positive, negative], 0),
            ([positive, {**positive, "sentiment": "negative"}], 0),
        ]:
            with self.subTest(observations=observations):
                rows = ReviewModel.normalize(json.dumps({"observations": observations}), texts, tags, evidence)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["value"], expected)
                self.assertEqual(rows[0]["quote"], texts["liked"])

    def test_atmosphere_requires_a_specific_description(self):
        tags = [dict(id=str(UUID(int=1)), name="Уютная атмосфера"), dict(id=str(UUID(int=2)), name="Мрачная атмосфера")]
        for text in (
            "Атмосферная книга",
            "Ну там в общем норм люди что-то ходят атмосфера есть",
            "1984 очень атмосферная",
        ):
            for tag in (1, 2):
                texts = {"liked": text}
                _, ordered, evidence = ReviewModel.prepare(texts, tags)
                content = json.dumps({"observations": [dict(tag=tag, evidence=1, sentiment="positive")]})
                self.assertEqual(ReviewModel.normalize(content, texts, ordered, evidence), [])
        for text, tag in (
            ("Ламповая домашняя обстановка", 1),
            ("Умиротворяющая атмосфера", 1),
            ("Гнетущая безысходность", 2),
            ("Cozy вайб очень зашёл", 1),
            ("Дарк атмосфера не моё", 2),
            ("Dark атмосфера", 2),
        ):
            texts = {"liked": text}
            _, ordered, evidence = ReviewModel.prepare(texts, tags)
            content = json.dumps({"observations": [dict(tag=tag, evidence=1, sentiment="positive")]})
            self.assertEqual(len(ReviewModel.normalize(content, texts, ordered, evidence)), 1)

    def test_slang_reactions_do_not_invent_features_or_call_provider(self):
        samples = [
            "Душно, герой NPC, местами кринж.",
            "Стекло, я ору.",
            "Автор cooked.",
            "POV: я дочитала.",
            "Имба, база, peak fiction.",
            "ГГ сигма, +1000 ауры, rizz.",
            "Лютый вайб.",
            "Скибиди делулу, я в тильте 💀",
            "Герой ред флаг",
            "💀😭",
        ]
        for text in samples:
            with self.subTest(text=text), patch("app.core.model.httpx.Client") as client:
                self.assertTrue(general_reaction(text))
                self.assertEqual(ReviewModel().analyze({"comment": text}, self.tags), [])
                client.assert_not_called()

    def test_concrete_features_are_not_filtered_as_slang(self):
        for text in (
            "Умный гг имба",
            "Плот твисты база",
            "Слоуберн между героями не зашёл",
            "Персонажи из врагов стали возлюбленными, обожаю",
            "Финал стекло, все погибли, не моё",
            "Медленно развиваются события, душно",
            "Кринжовый любовный треугольник",
            "Cozy атмосфера",
            "Мрачная атмосфера",
            "Скибиди, но умный герой понравился",
        ):
            with self.subTest(text=text):
                self.assertFalse(general_reaction(text))

    def test_slang_reaction_keeps_the_feature_and_original_quote(self):
        for separator in (" ", "   ", "\n", "\r\n"):
            texts = {"comment": "Умный герой." + separator + "Это имба!"}
            messages, tags, evidence = ReviewModel.prepare(texts, self.tags)
            self.assertEqual(evidence, [{"field": "comment", "text": texts["comment"]}])
            self.assertIn("Это имба!", messages[1]["content"])
            content = json.dumps({"observations": [dict(tag=1, evidence=1, sentiment="positive")]})
            self.assertEqual(ReviewModel.normalize(content, texts, tags, evidence)[0]["quote"], texts["comment"])

    def test_general_reaction_alone_cannot_confirm_a_tag(self):
        texts = {"liked": "Умный герой", "disliked": "Кринж"}
        _, tags, evidence = ReviewModel.prepare(texts, self.tags)
        self.assertEqual(len(evidence), 2)
        content = json.dumps({"observations": [dict(tag=1, evidence=2, sentiment="negative")]})
        self.assertEqual(ReviewModel.normalize(content, texts, tags, evidence), [])

    def test_invalid_observations_are_not_applied(self):
        texts = {"comment": "Текст."}
        _, tags, evidence = ReviewModel.prepare(texts, self.tags)
        valid = {"tag": 1, "evidence": 1, "sentiment": "positive"}
        invalid = [
            {**valid, "tag": 0},
            {**valid, "tag": 3},
            {**valid, "tag": "1"},
            {**valid, "tag": True},
            {**valid, "evidence": 0},
            {**valid, "evidence": 2},
            {**valid, "sentiment": "neutral"},
            {**valid, "sentiment": 0},
            {**valid, "sentiment": False},
            {**valid, "sentiment": "1"},
            {**valid, "quote": "Выдумка"},
        ]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                ReviewModel.normalize(json.dumps({"observations": [row]}), texts, tags, evidence)
        for content in [
            "```json\n{}\n```",
            '{"observations":',
            '{"signals":[]}',
            json.dumps({"observations": [valid] * (MAX_SIGNALS + 1)}),
        ]:
            with self.subTest(content=content[:40]), self.assertRaises(ValueError):
                ReviewModel.normalize(content, texts, tags, evidence)

    def test_empty_input_never_calls_provider(self):
        with patch("app.core.model.httpx.Client") as client:
            self.assertEqual(ReviewModel().analyze({"liked": " \n", "comment": None}, self.tags), [])
            self.assertEqual(ReviewModel().analyze({"comment": "Отзыв"}, []), [])
            client.assert_not_called()

    def test_provider_request_and_usage(self):
        settings = get_settings().model_copy(
            update={"yandex_model_uri": "gpt://folder/qwen3.6-35b-a3b/latest", "yandex_api_key": SecretStr("test-key")}
        )

        def handle(request):
            payload = json.loads(request.content)
            self.assertEqual(request.headers["x-session-id"], ReviewModel.cache_session(payload))
            self.assertEqual(payload["reasoning_effort"], "none")
            self.assertEqual(payload["max_tokens"], 256)
            self.assertNotIn(self.tags[0]["id"], str(payload))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps(
                                    {
                                        "observations": [{"tag": 1, "evidence": 1, "sentiment": "positive"}],
                                    }
                                )
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 20},
                },
            )

        client = httpx.Client(base_url="https://example.test/v1/", transport=httpx.MockTransport(handle))
        with (
            patch("app.core.model.get_settings", return_value=settings),
            patch("app.core.model.httpx.Client", return_value=client),
        ):
            model = ReviewModel()
            rows = model.analyze({"liked": "Тег А"}, self.tags)
        self.assertEqual(rows[0]["tag_id"], UUID(int=1))
        self.assertEqual(model.last_usage, {"prompt_tokens": 200, "completion_tokens": 20})

    def test_truncated_response_retains_usage_and_fails(self):
        client = httpx.Client(
            base_url="https://example.test/v1/",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [{"finish_reason": "length", "message": {"content": None}}],
                        "usage": {"prompt_tokens": 200, "completion_tokens": 1500},
                    },
                )
            ),
        )
        model = ReviewModel()
        model.model_uri = "gpt://folder/qwen3.6-35b-a3b/latest"
        settings = get_settings().model_copy(update={"yandex_api_key": SecretStr("test-key")})
        with (
            patch("app.core.model.get_settings", return_value=settings),
            patch("app.core.model.httpx.Client", return_value=client),
            self.assertRaises(ValueError),
        ):
            model.analyze({"comment": "Отзыв"}, self.tags)
        self.assertEqual(model.last_usage["completion_tokens"], 1500)
