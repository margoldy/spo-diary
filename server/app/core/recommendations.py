import math
from collections import defaultdict
from decimal import Decimal

BACKGROUND_WEIGHT = Decimal(".25")
RATING_VALUES = {1: Decimal("-.3"), 2: Decimal("-.2"), 4: Decimal(".2"), 5: Decimal(".3")}


def history_value(rating, signals):
    if rating is not None:
        return RATING_VALUES.get(rating, Decimal(0))
    return Decimal(".15") if sum(signals.values()) > 0 else Decimal(0)


def explicit_weights(profile, ratings):
    values = {tag: [Decimal(p), Decimal(n)] for tag, (p, n) in profile.items()}
    for row in ratings:
        tag, value = row["tag_id"], Decimal(row["value"])
        values[tag][0 if value > 0 else 1] -= abs(value)
    result = {}
    for tag, (positive, negative) in values.items():
        result[tag] = (positive - negative) / (2 + positive + negative)
    return result


def catalog_maps(tag_rows, genre_rows):
    tags, main, genres = defaultdict(set), defaultdict(set), defaultdict(set)
    for work_id, tag_id, is_main in tag_rows:
        tags[work_id].add(tag_id)
        if is_main:
            main[work_id].add(tag_id)
    for work_id, genre_id in genre_rows:
        genres[work_id].add(genre_id)
    return tags, main, genres


class ContentScores:
    def __init__(self, tags, main, genres, *, types=None, history=None):
        self.tags, self.main, self.genres = tags, main, genres
        self.types = types or {}
        self.history = history
        frequency = defaultdict(int)
        for values in tags.values():
            for tag in values:
                frequency[tag] += 1
        self.idf = {tag: 1 + math.log((len(tags) + 1) / (count + 1)) for tag, count in frequency.items()}
        self.rarity = {tag: Decimal(str(math.sqrt(value))) for tag, value in self.idf.items()}
        genre_frequency = defaultdict(int)
        for values in genres.values():
            for genre in values:
                genre_frequency[genre] += 1
        genre_count = sum(bool(values) for values in genres.values())
        self.genre_idf = {
            genre: 1 + math.log((genre_count + 1) / (count + 1)) for genre, count in genre_frequency.items()
        }

    def genre_similarity(self, left, right):
        if not left or not right:
            return 1.0
        return sum(self.genre_idf.get(g, 1) ** 2 for g in left & right) / math.sqrt(
            sum(self.genre_idf.get(g, 1) ** 2 for g in left)
            * sum(self.genre_idf.get(g, 1) ** 2 for g in right)
        )

    def similarity(self, source, target):
        left, right = self.main[source], self.main[target]
        if not left or not right:
            return 0.0
        genre_score = self.genre_similarity(self.genres[source], self.genres[target])
        numerator = sum(self.idf[tag] ** 2 for tag in left & right)
        denominator = math.sqrt(sum(self.idf[tag] ** 2 for tag in left) * sum(self.idf[tag] ** 2 for tag in right))
        return genre_score * numerator / denominator

    def type_factor(self, work_id):
        positive = [row for row in self.history or [] if row["value"] > 0]
        total = sum((row["value"] for row in positive), Decimal(0))
        same = sum(
            (row["value"] for row in positive if row["type_id"] == self.types.get(work_id)), Decimal(0)
        )
        return 1 + Decimal(".25") * same / (Decimal(".3") + total)

    def tag_context(self, tag, work_id):
        sources = [row for row in self.history or [] if row["signals"].get(tag, 0) > 0]
        if not sources:
            return Decimal(1)
        match = sum(self.genre_similarity(row["genres"], self.genres[work_id]) for row in sources) / len(sources)
        return Decimal(str(.5 + .5 * match))

    def source_contributions(self, row, work_id, weights):
        source = row["work_id"]
        source_tags, target_tags = self.main[source], self.main[work_id]
        genres = self.genre_similarity(row["genres"], self.genres[work_id])
        if not source_tags:
            # без разметки используем только известные жанры
            shared = row["genres"] & self.genres[work_id]
            total = sum(self.genre_idf.get(g, 1) ** 2 for g in shared)
            return {
                genre: row["value"] * Decimal(str(.25 * genres * self.genre_idf.get(genre, 1) ** 2 / total))
                for genre in shared
            }
        if not self.main[source].intersection(self.main[work_id]) or not genres:
            return {}
        left = {tag: self.idf[tag] for tag in source_tags}
        right = {tag: self.idf[tag] for tag in target_tags}
        norm = math.sqrt(sum(v * v for v in left.values()) * sum(v * v for v in right.values()))
        return {
            tag: row["value"] * Decimal(str(genres * left[tag] * right[tag] / norm))
            for tag in source_tags & target_tags
            if not weights.get(tag) and tag not in row["signals"]
        }

    def contributions(self, work_id, profile, ratings):
        weights = explicit_weights(profile, ratings)
        rarity = self.rarity
        total = sum((abs(value) for tag, value in weights.items() if tag in rarity), Decimal(0))
        # нормировка весов редких тегов
        scale = (
            sum((abs(value) * rarity[tag] for tag, value in weights.items() if tag in rarity), Decimal(0)) / total
            if total
            else Decimal(1)
        )
        main = self.main[work_id]
        background = self.tags[work_id] - main
        norm = (
            (Decimal(len(main)) + BACKGROUND_WEIGHT**2 * len(background)).sqrt() if main or background else Decimal(1)
        )
        result = {
            tag: weight * rarity[tag] / scale * (1 if tag in main or weight < 0 else BACKGROUND_WEIGHT) / norm
            for tag, weight in weights.items()
            if tag in self.tags[work_id]
        }
        result = {
            tag: value * self.tag_context(tag, work_id) if value > 0 else value
            for tag, value in result.items()
        }
        history = self.history
        if history is None:
            history = [
                dict(row, genres=self.genres[row["work_id"]], signals={})
                for row in {row["library_id"]: row for row in ratings}.values()
            ]
        strength = sum((abs(row["value"]) for row in history), Decimal(0))
        for row in history:
            for tag, value in self.source_contributions(row, work_id, weights).items():
                result[tag] = result.get(tag, Decimal(0)) + value / (2 + strength)
        factor = self.type_factor(work_id)
        return {tag: value * factor if value > 0 else value for tag, value in result.items()}

    def score(self, work_id, profile, ratings):
        return sum(self.contributions(work_id, profile, ratings).values(), Decimal(0))
