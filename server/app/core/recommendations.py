import math
from collections import defaultdict
from decimal import Decimal

BACKGROUND_WEIGHT = Decimal(".25")


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
    def __init__(self, tags, main, genres):
        self.tags, self.main, self.genres = tags, main, genres
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

    def similarity(self, source, target):
        left, right = self.main[source], self.main[target]
        if not left or not right:
            return 0.0
        source_genres, target_genres = self.genres[source], self.genres[target]
        genre_score = 1.0
        if source_genres and target_genres:
            genre_score = sum(self.genre_idf.get(g, 1) ** 2 for g in source_genres & target_genres) / math.sqrt(
                sum(self.genre_idf.get(g, 1) ** 2 for g in source_genres)
                * sum(self.genre_idf.get(g, 1) ** 2 for g in target_genres)
            )
        numerator = sum(self.idf[tag] ** 2 for tag in left & right)
        denominator = math.sqrt(sum(self.idf[tag] ** 2 for tag in left) * sum(self.idf[tag] ** 2 for tag in right))
        return genre_score * numerator / denominator

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
        sources = {row["library_id"]: row for row in ratings}
        strength = sum((abs(Decimal(row["value"])) for row in sources.values()), Decimal(0))
        for row in sources.values():
            source = row["work_id"]
            similarity = self.similarity(source, work_id)
            if not similarity:
                continue
            shared = self.main[source] & main
            shared_norm = sum(self.idf[tag] ** 2 for tag in shared)
            value = Decimal(row["value"]) * Decimal(str(similarity)) / (2 + strength)
            for tag in shared:
                # оценка не учитывается при явном отношении к тегу
                if weights.get(tag):
                    continue
                result[tag] = result.get(tag, Decimal(0)) + value * Decimal(str(self.idf[tag] ** 2 / shared_norm))
        return result

    def score(self, work_id, profile, ratings):
        return sum(self.contributions(work_id, profile, ratings).values(), Decimal(0))
