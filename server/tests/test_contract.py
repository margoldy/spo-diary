import json
import re
import unittest
from pathlib import Path

from app.api import auth, library, private_works, recommendations, users, works
from app.main import app

DOCUMENT = Path(__file__).resolve().parents[1] / "docs" / "API.md"


@unittest.skipUnless(DOCUMENT.is_file(), "docs/API.md отсутствует")
class ContractTests(unittest.TestCase):
    def test_routes_match_documentation(self):
        documented = set(re.findall(r"^### (GET|POST|PUT|PATCH|DELETE) (\S+)", DOCUMENT.read_text("utf-8"), re.M))
        actual = {
            (method.upper(), path.removeprefix("/api/v1"))
            for path, operations in app.openapi()["paths"].items()
            for method in operations
        }
        self.assertEqual(actual, documented)
        self.assertEqual(len(actual), 31)

    def test_complete_response_examples_match_schemas(self):
        models = {}
        for module in (auth, library, private_works, recommendations, users, works):
            for route in module.router.routes:
                for method in route.methods:
                    models[(method, route.path)] = route.response_model
        chunks = re.split(r"^### (GET|POST|PUT|PATCH|DELETE) (\S+)\s*$", DOCUMENT.read_text("utf-8"), flags=re.M)
        count = 0
        for index in range(1, len(chunks), 3):
            method, path, section = chunks[index : index + 3]
            model = models[(method, path)]
            if model is None:
                continue
            answer = re.search(r"(?:\*\*)?Ответ[^\n]*", section)
            if not answer:
                continue
            for example in re.findall(r"```json\s*\n(.*?)\n```", section[answer.end() :], re.S):
                with self.subTest(method=method, path=path):
                    model.model_validate(json.loads(example))
                    count += 1
        self.assertGreaterEqual(count, 28)

    def test_request_examples_match_schemas(self):
        models = {}
        for module in (auth, library, private_works, recommendations, users, works):
            for route in module.router.routes:
                if route.body_field is not None and route.body_field.field_info.media_type == "application/json":
                    for method in route.methods:
                        models[(method, route.path)] = route.body_field.field_info.annotation
        chunks = re.split(r"^### (GET|POST|PUT|PATCH|DELETE) (\S+)\s*$", DOCUMENT.read_text("utf-8"), flags=re.M)
        checked = set()
        for index in range(1, len(chunks), 3):
            method, path, section = chunks[index : index + 3]
            model = models.get((method, path))
            if model is None:
                continue
            request = re.split(r"(?:\*\*)?Ответ[^\n]*", section, maxsplit=1)[0]
            for example in re.findall(r"```json\s*\n(.*?)\n```", request, re.S):
                with self.subTest(method=method, path=path):
                    model.model_validate(json.loads(example))
                    checked.add((method, path))
        self.assertEqual(checked, set(models))


if __name__ == "__main__":
    unittest.main()
