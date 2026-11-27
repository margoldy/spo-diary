import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/works.json"
ORDER_HASH = "64e445a5c500a1530bcdc9cb8808ed2a034faead90e002558a4afb497c5cd78d"
TAG_HASH = "0323612f7a89236984b0eb28397a767e01d14e7d0744c8acab5f9f9603160313"
ANNOTATION_HASH = "08af5b1af89cbfe26afe2405683cd089fe12415f55761a8d25db218b52fddb7d"

# эталонные сценарии
# индексы произведений и тегов в каталоге
# 2: совпадение; 1: частичное совпадение; 0: не подходит
PROFILES = [
    dict(
        name="Командный спорт",
        need="Спортивная команда, тренировки и соревнования; романтика не должна быть основой истории.",
        signals={130: (3, 0), 55: (2, 0), 5: (1, 0), 13: (1, 0), 20: (0, 2)},
        library=[5],
        good=[21, 41, 85, 86, 89, 109, 126, 128, 153],
        partial=[111, 125, 180],
    ),
    dict(
        name="Расследования",
        need="Умный герой раскрывает загадки; важнее расследование, чем школьная романтика.",
        signals={0: (3, 0), 51: (3, 0), 86: (1, 0), 52: (1, 0), 20: (0, 2), 63: (0, 1)},
        library=[45],
        good=[17, 145, 177, 178, 179],
        partial=[10, 81, 149, 172],
    ),
    dict(
        name="Спокойная повседневность",
        need="Неспешная уютная жизнь, природа и небольшое сообщество; без акцента на мрачных событиях.",
        signals={97: (3, 0), 91: (2, 0), 62: (2, 0), 124: (1, 0), 99: (0, 2), 98: (0, 1)},
        library=[24],
        good=[26, 59, 61, 76, 77, 91, 122],
        partial=[28, 42, 48, 64, 65, 66, 70, 114, 163, 166, 180, 184],
    ),
    dict(
        name="Общество и нравственный выбор",
        need="Книги о неравенстве, общественном давлении и нравственных конфликтах, не школьные приключения.",
        signals={30: (3, 0), 33: (2, 0), 34: (2, 0), 6: (1, 0), 63: (0, 2)},
        types=["book"],
        library=[186],
        good=[172, 174, 187, 193, 194, 197, 198, 199],
        partial=[165, 169, 173, 188, 189, 190, 191, 192, 196],
    ),
    dict(
        name="Музыка и выступления",
        need="Музыканты учатся, репетируют и выступают; музыка должна быть существенной частью истории.",
        signals={125: (3, 0), 5: (2, 0), 57: (1, 0), 27: (0, 1)},
        library=[52],
        good=[2, 28, 79, 102, 118, 121],
        partial=[68],
    ),
    dict(
        name="Изменение прошлого",
        need="Перемещение информации или героя во времени, изменение прошлого и его последствий.",
        signals={72: (3, 0), 86: (2, 0), 85: (1, 0), 58: (1, 0), 97: (0, 1)},
        library=[73],
        good=[0, 43, 50, 95, 159],
        partial=[25, 92, 142],
    ),
    dict(
        name="Развитие сил и испытания",
        need="Как Solo Leveling: усиление героя, опасные испытания и сражения; романтика второстепенна.",
        signals={77: (3, 0), 127: (2, 0), 5: (1, 0), 121: (1, 0), 20: (0, 2)},
        library=[200],
        good=[158, 159, 201],
        partial=[53, 98, 107, 110, 133, 149, 155],
    ),
    dict(
        name="Практические книги",
        need="Понятные прикладные книги с заданиями для саморазвития, не художественные истории об успехе.",
        signals={110: (3, 0), 111: (2, 0), 116: (1, 0), 113: (1, 0)},
        types=["book"],
        library=[],
        good=[175, 176],
        partial=[],
    ),
]

# дополнительные сценарии
EXTRA_PROFILES = [
    dict(
        name="Родительство и семья",
        need="Забота о близких и семейные отношения.",
        signals={19: (3, 0), 11: (1, 0), 12: (1, 0), 63: (0, 1)},
        library=[48],
        good=[10, 81, 91, 112, 152, 169, 187, 97, 38, 14, 183, 194, 197],
        partial=[24, 120, 184, 163, 180],
    ),
    dict(
        name="Творческое призвание",
        need="Создание произведений, творческая работа и поиск своего пути.",
        signals={57: (3, 0), 5: (1, 0), 32: (1, 0)},
        library=[101],
        good=[78, 90, 116, 188, 189, 59, 68, 36, 123, 118, 52, 102, 79],
        partial=[2, 28, 121, 182, 40],
    ),
    dict(
        name="Путешествия и приключения",
        need="Дорога, опасные приключения и смелость; не повседневная работа.",
        signals={50: (3, 0), 9: (1, 0), 48: (1, 0), 59: (0, 2), 97: (0, 1)},
        library=[161],
        good=[39, 67, 69, 96, 148, 162, 164, 168, 173, 181, 75, 6, 119],
        partial=[16, 93, 47, 141, 171, 19, 138, 107],
    ),
    dict(
        name="Отношения вне школы",
        need="Отношения сложившейся пары, взрослая жизнь; без школьной романтики.",
        signals={21: (3, 0), 59: (1, 0), 63: (0, 3), 27: (0, 1)},
        library=[29],
        good=[99, 49, 117, 102, 188, 191, 193, 194],
        partial=[47, 141, 79, 196, 103],
    ),
]

VARIANTS = {
    "Текущие веса": {},
    "Сглаживание 1 вместо 2": {"prior": 1},
    "Сглаживание 4 вместо 2": {"prior": 4},
    "Штраф за минус ×2": {"negative_scale": 2},
    "Без деления на число тегов": {"power": 0},
    "Деление на число тегов": {"power": 1},
    "Редкие теги важнее (IDF)": {"idf": True},
}

# контрольные сценарии
CHECK_PROFILES = [
    dict(
        name="Наука и восстановление мира",
        need="Научные объяснения и применение знаний для восстановления жизни.",
        signals={58: (3, 0), 105: (3, 0), 66: (1, 0)},
        library=[8],
        good=[87, 171, 62],
        partial=[138, 150, 119, 122],
    ),
    dict(
        name="Обучение магии",
        need="Освоение магии, правила и помощь наставника.",
        signals={70: (3, 0), 15: (2, 0), 5: (2, 0)},
        library=[98],
        good=[60, 155, 159, 149, 32],
        partial=[53, 110, 133, 158, 147, 200, 201, 61, 58, 113],
    ),
    dict(
        name="Человек и природа",
        need="Конфликт людей с природой, экология и последствия разрушения мира.",
        signals={124: (3, 0), 37: (1, 0), 66: (1, 0)},
        library=[19],
        good=[138, 65, 181, 42, 114],
        partial=[67, 48, 87, 8, 27, 122, 119],
    ),
    dict(
        name="Искупление и ответственность",
        need="Герой признаёт прошлые ошибки и пытается исправить причинённый вред.",
        signals={8: (3, 0), 47: (2, 0)},
        library=[1],
        good=[83, 165, 187, 191],
        partial=[7, 143, 50, 43, 95, 172, 11],
    ),
]


def load_catalog(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    fingerprint = hashlib.sha256("\n".join(w["id"] for w in data["works"]).encode()).hexdigest()
    tag_fingerprint = hashlib.sha256("\n".join(t["id"] for t in data["tags"]).encode()).hexdigest()
    if fingerprint != ORDER_HASH or tag_fingerprint != TAG_HASH:
        raise ValueError("Порядок произведений или тегов не соответствует тестовым сценариям")
    return data


def weights(profile, tags, prior=2, rating_scale=1, **unused):
    signals = defaultdict(lambda: [0, 0])
    for index, counts in profile.get("signals", {}).items():
        signals[tags[index]["id"]] = list(counts)
    for work, rating in profile.get("ratings", []):
        value = {1: -0.3, 2: -0.2, 3: 0, 4: 0.2, 5: 0.3}[rating] * rating_scale
        for tag in work["tag_ids"]:
            signals[tag][0 if value > 0 else 1] += abs(value)
    return {tag: (p - n) / (prior + p + n) for tag, (p, n) in signals.items()}


def rank_old(profile, data, prior=2, power=0.5, negative_scale=1, idf=False, **options):
    works, tags = data["works"], data["tags"]
    coefficients = weights(profile, tags, prior=prior, **options)
    frequency = Counter(t for w in works for t in w["tag_ids"])
    available = [
        (i, w)
        for i, w in enumerate(works)
        if i not in profile.get("library", []) + profile.get("hidden", [])
        and (not profile.get("types") or w["type"] in profile["types"])
    ]
    scored = []
    for i, w in available:
        score = 0
        for tag in w["tag_ids"]:
            value = coefficients.get(tag, 0)
            if value < 0:
                value *= negative_scale
            if idf:
                value *= 1 + math.log((len(works) + 1) / (frequency[tag] + 1))
            score += value
        score /= max(1, len(w["tag_ids"])) ** power
        scored.append((i, score))
    personal = [(i, score) for i, score in scored if score > 1e-12]
    if personal:
        return sorted(personal, key=lambda r: (-r[1], works[r[0]]["title"].lower(), works[r[0]]["id"])), "personal"
    negative = {tag for tag, value in coefficients.items() if value < 0}
    return sorted(
        scored,
        key=lambda r: (
            bool(negative.intersection(works[r[0]]["tag_ids"])),
            works[r[0]]["title"].lower(),
            works[r[0]]["id"],
        ),
    ), "general"


def rank(profile, data, *, baseline=False):
    sys.path.insert(0, str(ROOT))
    from app.core.recommendations import ContentScores, catalog_maps
    from app.db.seed import GENRE_MAP

    works, tags = data["works"], data["tags"]
    tag_map, main_map, genre_map = catalog_maps(
        [(w["id"], tag, tag in w.get("main_tag_ids", w["tag_ids"])) for w in works for tag in w["tag_ids"]],
        [(w["id"], g) for w in works for name in w["genres"] for g in GENRE_MAP.get(name, [name])],
    )
    counts = defaultdict(lambda: [0, 0])
    for index, (positive, negative) in profile.get("signals", {}).items():
        counts[tags[index]["id"]] = [positive, negative]
    ratings = []
    for entry_id, (work, rating) in enumerate(profile.get("ratings", [])):
        value = {1: -0.3, 2: -0.2, 3: 0, 4: 0.2, 5: 0.3}[rating]
        if not value:
            continue
        for tag in work.get("main_tag_ids", work["tag_ids"]):
            from decimal import Decimal

            value = Decimal(str(value))
            counts[tag][0 if value > 0 else 1] += abs(value)
            ratings.append(
                dict(tag_id=tag, value=value, genres=genre_map[work["id"]], work_id=work["id"], library_id=entry_id)
            )
    scorer = ContentScores(tag_map, main_map, genre_map)
    if baseline:
        # старая формула на той же разметке без поправок на редкость
        from decimal import Decimal

        scorer.rarity = dict.fromkeys(scorer.rarity, Decimal(1))
        scorer.genre_idf = dict.fromkeys(scorer.genre_idf, 1.0)
    scored = [
        (i, float(scorer.score(w["id"], counts, ratings)))
        for i, w in enumerate(works)
        if i not in profile.get("library", []) + profile.get("hidden", [])
        and (not profile.get("types") or w["type"] in profile["types"])
    ]
    personal = [(i, s) for i, s in scored if s > 1e-12]
    has_preferences = any(v > 0 for v in weights(profile, tags).values())
    if personal or has_preferences:
        return sorted(
            personal, key=lambda row: (-row[1], works[row[0]]["title"].lower(), works[row[0]]["id"])
        ), "personal"
    negative = {tag for tag, v in weights(profile, tags).items() if v < 0}
    return sorted(
        scored,
        key=lambda row: (
            bool(negative.intersection(works[row[0]]["tag_ids"])),
            works[row[0]]["title"].lower(),
            works[row[0]]["id"],
        ),
    ), "general"


def grade(profile, index):
    return 2 if index in profile["good"] else int(index in profile["partial"])


def metrics(profile, ranking, works):
    top = ranking[:5]
    grades = [grade(profile, i) for i, _ in top]
    available = [
        i
        for i, w in enumerate(works)
        if i not in profile.get("library", []) + profile.get("hidden", [])
        and (not profile.get("types") or w["type"] in profile["types"])
    ]
    ideal = sorted((grade(profile, i) for i in available), reverse=True)[:5]

    def dcg(values):
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(values))

    groups = {works[i].get("group_id") or works[i]["id"] for i, _ in top}
    return {
        "strict_p5": sum(g == 2 for g in grades) / 5,
        "ndcg5": dcg(grades) / dcg(ideal) if dcg(ideal) else 0,
        "shown": len(top),
        "stories": len(groups),
        "relevant_available": sum(grade(profile, i) == 2 for i in available),
    }


def verify_database(data):
    sys.path.insert(0, str(ROOT))
    from decimal import Decimal
    from uuid import UUID

    from sqlalchemy import delete, select, text
    from sqlalchemy.orm import Session
    from test_api import ApiFixture

    from app.core.reference import TYPE_IDS
    from app.db.models import Hidden, Library, LibraryTag, Recommendation, UserTag, Work, WorkGenre, WorkTag
    from app.db.queries.preferences import PreferencesQueries
    from app.db.queries.recommendations import RecommendationsQueries
    from app.db.seed import GENRE_MAP, GENRE_NAMES
    from app.db.session import get_engine
    from app.schemas.common import RecommendationsQuery
    from app.services.recommendations import RecommendationsService

    fixture = ApiFixture()
    fixture.setUpClass()
    fixture.setUp()
    try:
        engine = get_engine()
        if engine.url.database != "spo_diary_test":
            raise RuntimeError("Проверка разрешена только в spo_diary_test")
        works, tags = data["works"], data["tags"]
        with Session(engine) as db:
            db.execute(text("TRUNCATE works, work_groups CASCADE"))
            db.add_all([Work(id=UUID(w["id"]), title=w["title"], type_id=TYPE_IDS[w["type"]]) for w in works])
            db.flush()
            db.add_all(
                [
                    WorkTag(work_id=UUID(w["id"]), tag_id=UUID(t), is_main=t in w["main_tag_ids"])
                    for w in works
                    for t in w["tag_ids"]
                ]
            )
            db.add_all(
                [
                    WorkGenre(work_id=UUID(w["id"]), genre_id=g)
                    for w in works
                    for g in {GENRE_NAMES[v] for name in w["genres"] for v in GENRE_MAP.get(name, [name])}
                ]
            )
            db.commit()
        scenarios = list(PROFILES + EXTRA_PROFILES + CHECK_PROFILES)
        for p in [p for p in PROFILES + EXTRA_PROFILES if p["library"]]:
            scenarios.append(
                dict(p, name=p["name"] + " (только оценка)", signals={}, ratings=[(works[p["library"][0]], 5)])
            )
        scenarios += [
            dict(name="Нет предпочтений"),
            dict(name="Только минусы", signals={20: (0, 1), 63: (0, 1)}),
            dict(name="Плюс и минус сократились", signals={125: (1, 1)}),
            dict(name="Отметки произведения", signals={125: (1, 0), 63: (0, 1)}),
            dict(name="Нет тайтлов с выбранным тегом", signals={76: (1, 0)}),
            dict(name="Всё скрыто", signals={125: (1, 0)}, hidden=list(range(len(works)))),
        ]
        for profile in scenarios:
            with Session(engine) as db:
                for model in (Recommendation, UserTag, Library, Hidden):
                    db.execute(delete(model).where(model.user_id == fixture.user_id))
                signals = defaultdict(lambda: [Decimal(0), Decimal(0)])
                for index, counts in profile.get("signals", {}).items():
                    signals[tags[index]["id"]] = [Decimal(str(n)) for n in counts]
                for work, rating in profile.get("ratings", []):
                    value = Decimal(str({1: -0.3, 2: -0.2, 3: 0, 4: 0.2, 5: 0.3}[rating]))
                    for tag in work["main_tag_ids"]:
                        signals[tag][0 if value > 0 else 1] += abs(value)
                for tag in signals:
                    positive, negative = signals[tag]
                    db.add(
                        UserTag(
                            user_id=fixture.user_id,
                            tag_id=UUID(tag),
                            positive=positive,
                            negative=negative,
                        )
                    )
                db.add_all(
                    [Library(user_id=fixture.user_id, work_id=UUID(works[i]["id"])) for i in profile.get("library", [])]
                )
                db.add_all(
                    [Hidden(user_id=fixture.user_id, work_id=UUID(works[i]["id"])) for i in profile.get("hidden", [])]
                )
                db.flush()
                for work, rating in profile.get("ratings", []):
                    entry = db.scalar(
                        select(Library).where(Library.user_id == fixture.user_id, Library.work_id == UUID(work["id"]))
                    )
                    entry.rating = rating
                    value = Decimal(str({1: -0.3, 2: -0.2, 3: 0, 4: 0.2, 5: 0.3}[rating]))
                    if value:
                        db.add_all(
                            [
                                LibraryTag(library_id=entry.id, tag_id=UUID(tag), value=value, source="rating")
                                for tag in work["main_tag_ids"]
                            ]
                        )
                db.flush()
                PreferencesQueries(db).rescore(fixture.user_id)
                scores = dict(
                    db.execute(
                        select(Recommendation.work_id, Recommendation.score).where(
                            Recommendation.user_id == fixture.user_id
                        )
                    ).all()
                )
                ranking, expected_mode = rank(profile, data)
                actual = []
                for offset in range(0, len(works), 100):
                    rows, total, mode = RecommendationsQueries(db).page(
                        fixture.user_id, RecommendationsQuery(types=profile.get("types", []), limit=100, offset=offset)
                    )
                    actual.extend(str(w.id) for w in rows)
                assert total == len(ranking) and mode == expected_mode, profile["name"]
                assert set(actual) == {works[i]["id"] for i, _ in ranking}, profile["name"]
                if mode == "personal":
                    actual_scores = [float(scores[UUID(wid)]) for wid in actual]
                    assert all(math.isclose(a, b, abs_tol=1e-10) for a, (_, b) in zip(actual_scores, ranking)), profile[
                        "name"
                    ]
                    actual_top = actual[:5]
                    expected_top = [works[i]["id"] for i, _ in ranking[:5]]
                    assert actual_top == expected_top, (profile["name"], "Порядок равных баллов отличается")
                    response = RecommendationsService(db).list(
                        fixture.user_id, RecommendationsQuery(types=profile.get("types", []), limit=5)
                    )
                    assert len(response["items"]) == min(5, total)
                    assert all(item["reason"]["text"] for item in response["items"])
                db.rollback()
        return len(scenarios)
    finally:
        fixture.tearDown()
        fixture.tearDownClass()


def quality_results(data, *, baseline=False):
    results = {}
    for profile in PROFILES + EXTRA_PROFILES:
        variants = [("explicit", profile)]
        if profile["library"]:
            variants.append(("rating", dict(profile, signals={}, ratings=[(data["works"][profile["library"][0]], 5)])))
        for kind, candidate in variants:
            key = profile["name"] + " / " + kind
            results[key] = metrics(profile, rank(candidate, data, baseline=baseline)[0], data["works"])["ndcg5"]
    return results


def verify_quality(data):
    payload = [{k: w[k] for k in ("id", "tag_ids", "main_tag_ids", "genres")} for w in data["works"]]
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert digest == ANNOTATION_HASH, "Разметка не соответствует контрольной сумме"
    for work in data["works"]:
        assert set(work["main_tag_ids"]) <= set(work["tag_ids"])
    results = quality_results(data)
    before = quality_results(data, baseline=True)
    # сравниваем формулы на одной разметке
    assert sum(results.values()) >= sum(before.values())
    assert results["Музыка и выступления / explicit"] == 1
    assert results["Музыка и выступления / rating"] == 1
    assert results["Развитие сил и испытания / rating"] >= before["Развитие сил и испытания / rating"]
    return results


def report(data):
    current, before = quality_results(data), quality_results(data, baseline=True)
    lines = [
        "# Проверка рекомендаций", "",
        f"Каталог: {len(data['works'])} произведения. Проверка: {len(current)} сценария и {len(CHECK_PROFILES)} контрольных запроса.",
        "Метрика: nDCG@5, диапазон [0, 1]. Эталонные результаты заданы в тестах.", "",
        "| Сценарий | Отзывы и отметки | Только оценка |", "|---|---:|---:|",
    ]
    for profile in PROFILES + EXTRA_PROFILES:
        explicit = current[profile["name"] + " / explicit"]
        rating = current.get(profile["name"] + " / rating")
        right = f"{rating:.3f}" if rating is not None else "нет"
        lines.append(f"| {profile['name']} | {explicit:.3f} | {right} |")
    lines += [
        "",
        f"Среднее: {sum(current.values()) / len(current):.3f}; у предыдущей формулы на тех же данных: {sum(before.values()) / len(before):.3f}.",
        "",
        "Ограничения: межжанровые совпадения тегов, неопределённость предпочтений по одной оценке, несколько адаптаций в выдаче. Результаты относятся к тестовым сценариям; пользовательское исследование не проводилось.",
        "",
        "Запуск из `server`:", "", "```powershell",
        "app/.venv/Scripts/python.exe tests/evaluate_recommendations.py --verify-db --output ../../RECOMMENDATIONS_CHECK.md",
        "```", "",
        "`--verify-db` использует только `spo_diary_test`. Платная модель не вызывается.", "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-db", action="store_true")
    args = parser.parse_args()
    data = load_catalog(CATALOG)
    if args.verify_db:
        print(f"Сценарии с БД: {verify_database(data)}")
    print(f"Сценарии ранжирования: {len(verify_quality(data))}; контрольные: {len(CHECK_PROFILES)}")
    result = report(data)
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result)
