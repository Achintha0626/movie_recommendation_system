import json
import math
import re

import numpy as np
import pandas as pd

from services.semantic_similarity_service import SemanticSimilarityError


SEMANTIC_WEIGHT = 0.45
METADATA_WEIGHT = 0.25
COLLECTION_WEIGHT = 0.10
KEYWORD_WEIGHT = 0.10
POPULARITY_WEIGHT = 0.05
VOTE_AVERAGE_WEIGHT = 0.05
CANDIDATE_POOL_SIZE = 100
TITLE_STOP_WORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "in",
    "to",
    "for",
    "part",
    "movie",
    "film",
    "world",
}
KEYWORD_STOP_WORDS = {
    "3d",
    "animal",
    "attack",
    "based",
    "book",
    "film",
    "movie",
    "novel",
    "part",
    "sequel",
}
GENRE_WEIGHTS = {
    "action": 1.0,
    "adventure": 0.8,
    "comedy": 1.0,
    "crime": 1.5,
    "drama": 0.6,
    "family": 0.8,
    "fantasy": 1.4,
    "horror": 1.6,
    "mystery": 1.4,
    "romance": 1.2,
    "sci-fi": 2.0,
    "science fiction": 2.0,
    "thriller": 1.2,
    "war": 1.4,
    "western": 1.4,
}
DISTINCTIVE_GENRES = {
    "action",
    "crime",
    "fantasy",
    "horror",
    "mystery",
    "sci-fi",
    "science fiction",
    "thriller",
    "war",
    "western",
}
KNOWN_TMDB_GENRES = [
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "History",
    "Horror",
    "Music",
    "Mystery",
    "Romance",
    "Science Fiction",
    "TV Movie",
    "Thriller",
    "War",
    "Western",
]
WORD_RE = re.compile(r"[a-z0-9]+")


class HybridRankingError(RuntimeError):
    pass


class HybridRankingService:

    def __init__(self, dataframe, metadata_similarity, semantic_similarity):
        self.dataframe = dataframe.reset_index(drop=True)
        self.metadata_similarity = np.asarray(metadata_similarity, dtype=float)
        self.semantic_similarity = semantic_similarity
        self.validate()
        self._prepare_metadata_signals()

    def validate(self):
        movie_count = len(self.dataframe)

        if self.metadata_similarity.ndim != 2:
            raise HybridRankingError(
                "Metadata similarity matrix must be two-dimensional."
            )

        if self.metadata_similarity.shape != (movie_count, movie_count):
            raise HybridRankingError(
                "Metadata similarity dimensions do not match dataframe length: "
                f"matrix={self.metadata_similarity.shape}, dataframe={movie_count}"
            )

        try:
            self.semantic_similarity.validate()
        except SemanticSimilarityError as e:
            raise HybridRankingError(str(e)) from e

        semantic_shape = self.semantic_similarity.embeddings.shape
        if semantic_shape[0] != movie_count:
            raise HybridRankingError(
                "Semantic embedding row count does not match dataframe length: "
                f"embeddings={semantic_shape[0]}, dataframe={movie_count}"
            )

        if semantic_shape[1] <= 0:
            raise HybridRankingError(
                "Semantic embeddings must have at least one dimension."
            )

    def recommend(self, selected_index, genre_filter=None, limit=10):
        selected_index = int(selected_index)
        self._validate_index(selected_index)

        all_semantic_scores = self.semantic_similarity.similarity_scores(
            selected_index
        )
        semantic_scores = dict(
            sorted(
                all_semantic_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:CANDIDATE_POOL_SIZE]
        )
        metadata_scores = dict(
            self._top_metadata_scores(selected_index, CANDIDATE_POOL_SIZE)
        )
        candidate_indices = self._merge_candidate_indices(
            metadata_scores,
            semantic_scores,
            self._franchise_candidate_indices(selected_index),
        )

        if genre_filter:
            candidate_indices = [
                candidate_index
                for candidate_index in candidate_indices
                if self._has_genre(candidate_index, genre_filter)
            ]

        metadata_values = {
            index: self._safe_score(
                metadata_scores.get(index, self.metadata_similarity[selected_index, index])
            )
            for index in candidate_indices
        }
        semantic_values = {
            index: self._safe_score(all_semantic_scores.get(index, 0.0))
            for index in candidate_indices
        }
        metadata_normalized = self._normalize_values(metadata_values)
        semantic_normalized = self._normalize_values(semantic_values)

        ranked = []

        for candidate_index in candidate_indices:
            parts = self._score_parts(
                selected_index,
                candidate_index,
                semantic_normalized.get(candidate_index, 0.0),
                metadata_normalized.get(candidate_index, 0.0),
            )
            final_score = self._hybrid_score(parts)

            ranked.append({
                "index": candidate_index,
                "title": self._title(candidate_index),
                "score": final_score,
                "match_score": self._match_score(final_score),
                "reasons": self._reasons(
                    selected_index,
                    candidate_index,
                    parts,
                ),
                "parts": parts,
            })

        ranked.sort(
            key=lambda item: (
                item["score"],
                item["parts"]["collection"],
                item["parts"]["semantic"],
                item["parts"]["keyword"],
                item["parts"]["metadata"],
            ),
            reverse=True,
        )

        return ranked[:limit]

    def _prepare_metadata_signals(self):
        self.collections = self._column("collection").apply(self._normalize_text)
        self.title_tokens = self._column("original_title").apply(
            self._important_title_tokens
        )
        self.genre_names = self._column("genres").apply(self._parse_genres)
        self.genre_keys = self.genre_names.apply(
            lambda genres: frozenset(genre.casefold() for genre in genres)
        )
        self.keyword_tokens = self._column("keywords").apply(
            self._parse_keyword_tokens
        )
        self.cast_names = self._column("cast").apply(self._parse_names)
        self.director_names = self._column("crew").apply(self._parse_directors)
        self.popularity = self._normalize_series(self._numeric_column("popularity"))
        self.vote_average = (
            self._numeric_column("vote_average") / 10
        ).clip(0.0, 1.0)

    def _top_metadata_scores(self, selected_index, limit):
        scores = np.asarray(self.metadata_similarity[selected_index], dtype=float)
        candidates = [
            (index, self._safe_score(score))
            for index, score in enumerate(scores)
            if index != selected_index and np.isfinite(score)
        ]
        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates[:limit]

    def _merge_candidate_indices(
        self,
        metadata_scores,
        semantic_scores,
        franchise_indices,
    ):
        merged = []
        seen = set()

        for index in (
            list(metadata_scores.keys()) +
            list(semantic_scores.keys()) +
            list(franchise_indices)
        ):
            if index in seen:
                continue

            seen.add(index)
            merged.append(index)

        return merged

    def _franchise_candidate_indices(self, selected_index):
        selected_collection = self.collections.iloc[selected_index]
        selected_title_tokens = self.title_tokens.iloc[selected_index]
        candidates = []

        for candidate_index in range(len(self.dataframe)):
            if candidate_index == selected_index:
                continue

            candidate_collection = self.collections.iloc[candidate_index]
            if (
                selected_collection and
                candidate_collection and
                selected_collection == candidate_collection
            ):
                candidates.append(candidate_index)
                continue

            if selected_title_tokens & self.title_tokens.iloc[candidate_index]:
                candidates.append(candidate_index)

        return candidates

    def _score_parts(
        self,
        selected_index,
        candidate_index,
        semantic_score,
        metadata_score,
    ):
        collection_score, same_collection, title_score = self._collection_score(
            selected_index,
            candidate_index,
        )
        keyword_score = self._jaccard(
            self.keyword_tokens.iloc[selected_index],
            self.keyword_tokens.iloc[candidate_index],
        )
        genre_score = self._genre_overlap(
            self.genre_keys.iloc[selected_index],
            self.genre_keys.iloc[candidate_index],
        )
        specific_genre_match = self._specific_genre_match(
            self.genre_keys.iloc[selected_index],
            self.genre_keys.iloc[candidate_index],
        )

        if not specific_genre_match:
            genre_score = 0.0
            metadata_score *= 0.75

        metadata_signal = (
            (metadata_score * 0.65) +
            (genre_score * 0.35)
        )

        return {
            "semantic": semantic_score,
            "metadata": metadata_signal,
            "metadata_similarity": metadata_score,
            "collection": collection_score,
            "same_collection": same_collection,
            "title": title_score,
            "keyword": keyword_score,
            "genre": genre_score,
            "specific_genre_match": specific_genre_match,
            "popularity": float(self.popularity.iloc[candidate_index]),
            "vote_average": float(self.vote_average.iloc[candidate_index]),
        }

    def _hybrid_score(self, parts):
        return max(
            0.0,
            min(
                1.0,
                (SEMANTIC_WEIGHT * parts["semantic"]) +
                (METADATA_WEIGHT * parts["metadata"]) +
                (COLLECTION_WEIGHT * parts["collection"]) +
                (KEYWORD_WEIGHT * parts["keyword"]) +
                (POPULARITY_WEIGHT * parts["popularity"]) +
                (VOTE_AVERAGE_WEIGHT * parts["vote_average"]),
            ),
        )

    def _collection_score(self, selected_index, candidate_index):
        selected_collection = self.collections.iloc[selected_index]
        candidate_collection = self.collections.iloc[candidate_index]

        if (
            selected_collection and
            candidate_collection and
            selected_collection == candidate_collection
        ):
            return 1.0, True, 0.0

        title_score = self._overlap(
            self.title_tokens.iloc[selected_index],
            self.title_tokens.iloc[candidate_index],
        )

        return min(0.85, title_score * 0.85), False, title_score

    def _reasons(self, selected_index, candidate_index, parts):
        reasons = []

        if parts["same_collection"]:
            reasons.append("Same franchise")
        elif parts["title"] > 0:
            reasons.append("Similar title/franchise")

        if parts["semantic"] >= 0.55:
            reasons.append("Semantically similar story")

        if parts["genre"] > 0:
            reasons.append("Similar genre")

        if parts["keyword"] > 0:
            reasons.append("Similar keywords")

        if self.cast_names.iloc[selected_index] & self.cast_names.iloc[candidate_index]:
            reasons.append("Shared cast")

        if (
            self.director_names.iloc[selected_index] &
            self.director_names.iloc[candidate_index]
        ):
            reasons.append("Same director")

        if parts["popularity"] >= 0.70 or parts["vote_average"] >= 0.72:
            reasons.append("Popular/high-rated movie")

        return reasons or ["Semantically similar story"]

    def _match_score(self, score):
        return int(max(0, min(99, round(score * 99))))

    def _has_genre(self, candidate_index, genre_filter):
        normalized_filter = genre_filter.casefold()
        return any(
            genre.casefold() == normalized_filter
            for genre in self.genre_names.iloc[candidate_index]
        )

    def _title(self, index):
        title = self.dataframe["original_title"].iloc[index]
        return "" if pd.isna(title) else str(title)

    def _column(self, column_name):
        if column_name not in self.dataframe:
            return pd.Series([""] * len(self.dataframe), index=self.dataframe.index)

        return self.dataframe[column_name]

    def _numeric_column(self, column_name):
        if column_name not in self.dataframe:
            return pd.Series([0.0] * len(self.dataframe), index=self.dataframe.index)

        return pd.to_numeric(self.dataframe[column_name], errors="coerce").fillna(0.0)

    def _normalize_series(self, series):
        min_value = series.min()
        max_value = series.max()

        if max_value <= min_value:
            return pd.Series([0.0] * len(series), index=series.index)

        return ((series - min_value) / (max_value - min_value)).clip(0.0, 1.0)

    def _normalize_values(self, values):
        if not values:
            return {}

        finite_values = {
            index: value
            for index, value in values.items()
            if math.isfinite(value)
        }

        if not finite_values:
            return {index: 0.0 for index in values}

        min_value = min(finite_values.values())
        max_value = max(finite_values.values())

        if max_value <= min_value:
            return {index: 0.0 for index in values}

        return {
            index: max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))
            for index, value in values.items()
        }

    def _parse_genres(self, raw_genres):
        if self._is_empty(raw_genres):
            return ()

        try:
            genres = json.loads(raw_genres) if isinstance(raw_genres, str) else raw_genres
        except (json.JSONDecodeError, TypeError):
            return self._parse_plain_genres(str(raw_genres))

        if not isinstance(genres, list):
            return self._parse_plain_genres(str(raw_genres))

        names = []
        for genre in genres:
            name = genre.get("name") if isinstance(genre, dict) else genre
            if not isinstance(name, str) or not name.strip():
                continue

            names.append(self._normalize_genre(name))

        return tuple(dict.fromkeys(names))

    def _parse_plain_genres(self, raw_genres):
        normalized = raw_genres.casefold()
        names = [
            self._normalize_genre(genre)
            for genre in KNOWN_TMDB_GENRES
            if genre.casefold() in normalized
        ]

        if names:
            return tuple(dict.fromkeys(names))

        return tuple(
            dict.fromkeys(
                part.strip().title()
                for part in re.split(r"[,|;/]+", raw_genres)
                if part.strip()
            )
        )

    def _normalize_genre(self, name):
        clean_name = name.strip()
        return "Sci-Fi" if clean_name.casefold() == "science fiction" else clean_name

    def _parse_keyword_tokens(self, raw_keywords):
        if self._is_empty(raw_keywords):
            return frozenset()

        try:
            keywords = (
                json.loads(raw_keywords)
                if isinstance(raw_keywords, str)
                else raw_keywords
            )
        except (json.JSONDecodeError, TypeError):
            return frozenset(self._keyword_tokens(raw_keywords))

        if not isinstance(keywords, list):
            return frozenset(self._keyword_tokens(raw_keywords))

        tokens = []

        for keyword in keywords:
            if isinstance(keyword, dict):
                keyword = keyword.get("name")

            tokens.extend(self._keyword_tokens(keyword))

        return frozenset(tokens)

    def _keyword_tokens(self, text):
        return [
            token
            for token in self._word_tokens(text)
            if token not in KEYWORD_STOP_WORDS
        ]

    def _parse_names(self, raw_items):
        if self._is_empty(raw_items):
            return frozenset()

        try:
            items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
        except (json.JSONDecodeError, TypeError):
            return frozenset({str(raw_items).strip().casefold()})

        if not isinstance(items, list):
            return frozenset({str(raw_items).strip().casefold()})

        return frozenset(
            name.strip().casefold()
            for item in items
            if isinstance(item, dict)
            and isinstance((name := item.get("name")), str)
            and name.strip()
        )

    def _parse_directors(self, raw_crew):
        if self._is_empty(raw_crew):
            return frozenset()

        try:
            crew = json.loads(raw_crew) if isinstance(raw_crew, str) else raw_crew
        except (json.JSONDecodeError, TypeError):
            return frozenset({str(raw_crew).strip().casefold()})

        if not isinstance(crew, list):
            return frozenset({str(raw_crew).strip().casefold()})

        return frozenset(
            member["name"].strip().casefold()
            for member in crew
            if isinstance(member, dict)
            and member.get("job") == "Director"
            and isinstance(member.get("name"), str)
            and member["name"].strip()
        )

    def _important_title_tokens(self, title):
        return frozenset(
            token
            for token in self._word_tokens(title)
            if len(token) > 1 and token not in TITLE_STOP_WORDS
        )

    def _word_tokens(self, text):
        if self._is_empty(text):
            return []

        return WORD_RE.findall(str(text).casefold())

    def _normalize_text(self, value):
        if self._is_empty(value):
            return ""

        return str(value).strip().casefold()

    def _safe_score(self, value):
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        return score if math.isfinite(score) else 0.0

    def _overlap(self, selected_values, candidate_values):
        if not selected_values or not candidate_values:
            return 0.0

        return len(selected_values & candidate_values) / len(selected_values)

    def _jaccard(self, selected_values, candidate_values):
        if not selected_values or not candidate_values:
            return 0.0

        shared_count = len(selected_values & candidate_values)
        if shared_count == 0:
            return 0.0

        denominator = min(len(selected_values), len(candidate_values), 8)
        return min(1.0, shared_count / denominator)

    def _genre_overlap(self, selected_values, candidate_values):
        if not selected_values or not candidate_values:
            return 0.0

        selected_weight = sum(
            GENRE_WEIGHTS.get(genre, 1.0)
            for genre in selected_values
        )

        if selected_weight <= 0:
            return 0.0

        shared_weight = sum(
            GENRE_WEIGHTS.get(genre, 1.0)
            for genre in selected_values & candidate_values
        )

        return min(1.0, shared_weight / selected_weight)

    def _specific_genre_match(self, selected_values, candidate_values):
        selected_specific = selected_values & DISTINCTIVE_GENRES

        if not selected_specific:
            return True

        return bool(selected_specific & candidate_values)

    def _is_empty(self, value):
        return value is None or (isinstance(value, float) and pd.isna(value))

    def _validate_index(self, selected_index):
        if selected_index < 0 or selected_index >= len(self.dataframe):
            raise HybridRankingError(
                f"Selected movie index out of range: {selected_index}"
            )
