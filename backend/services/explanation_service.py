import json
import math
import re
from collections import OrderedDict


WORD_RE = re.compile(r"[a-z0-9]+")
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
    "film",
    "movie",
    "part",
    "sequel",
}
OVERVIEW_STOP_WORDS = {
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "and",
    "are",
    "but",
    "for",
    "from",
    "has",
    "have",
    "her",
    "his",
    "into",
    "its",
    "new",
    "not",
    "now",
    "one",
    "out",
    "she",
    "that",
    "the",
    "their",
    "them",
    "then",
    "this",
    "through",
    "when",
    "while",
    "who",
    "with",
    "world",
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


class ExplanationService:
    def __init__(self, max_cache_size=2048):
        self.max_cache_size = max_cache_size
        self._cache = OrderedDict()

    def explain(self, selected_movie, recommended_movie, signals):
        selected = self._row_to_dict(selected_movie)
        recommended = self._row_to_dict(recommended_movie)
        signals = signals or {}
        cache_key = self._cache_key(selected, recommended, signals)

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        explanation = self._build_explanation(selected, recommended, signals)
        self._cache[cache_key] = explanation

        if len(self._cache) > self.max_cache_size:
            self._cache.popitem(last=False)

        return explanation

    def _build_explanation(self, selected, recommended, signals):
        selected_title = self._title(selected)
        recommended_title = self._title(recommended)
        shared_genres = self._shared(
            self._parse_genres(selected.get("genres")),
            self._parse_genres(recommended.get("genres")),
        )
        shared_keywords = self._shared(
            self._parse_keywords(selected.get("keywords")),
            self._parse_keywords(recommended.get("keywords")),
        )
        shared_overview_terms = self._shared_overview_terms(
            selected,
            recommended,
        )
        shared_cast = self._shared(
            self._parse_names(selected.get("cast")),
            self._parse_names(recommended.get("cast")),
        )
        shared_directors = self._shared(
            self._parse_directors(selected.get("crew")),
            self._parse_directors(recommended.get("crew")),
        )
        same_collection = self._same_collection(selected, recommended, signals)
        title_related = self._safe_float(signals.get("title")) > 0
        semantic_score = self._safe_float(signals.get("semantic"))
        metadata_score = max(
            self._safe_float(signals.get("metadata")),
            self._safe_float(signals.get("metadata_similarity")),
        )

        links = []

        if same_collection:
            links.append("the same franchise")
        elif title_related:
            links.append("a similar franchise/title thread")

        if shared_keywords:
            links.append(f"themes like {self._format_list(shared_keywords[:3])}")

        if shared_genres:
            links.append(f"the {self._format_list(shared_genres[:2])} genres")

        if semantic_score >= 0.55:
            links.append("a closely related story premise")
        elif metadata_score >= 0.55:
            links.append("similar metadata patterns")

        if not links and shared_overview_terms:
            links.append(f"story ideas around {self._format_list(shared_overview_terms[:3])}")

        if not links:
            links.append("similar story and audience signals")

        first_sentence = (
            f"Like {selected_title}, {recommended_title} connects through "
            f"{self._format_list(links[:3])}."
        )
        supporting = self._supporting_sentence(
            shared_cast,
            shared_directors,
            shared_overview_terms,
            shared_keywords,
            semantic_score,
            metadata_score,
        )
        explanation = " ".join(
            sentence for sentence in (first_sentence, supporting) if sentence
        )

        return self._limit_words(explanation, 60)

    def _supporting_sentence(
        self,
        shared_cast,
        shared_directors,
        shared_overview_terms,
        shared_keywords,
        semantic_score,
        metadata_score,
    ):
        if shared_directors:
            return f"Both are tied to {self._format_list(shared_directors[:2])} behind the camera."

        if shared_cast:
            return f"Shared cast such as {self._format_list(shared_cast[:2])} adds another connection."

        if shared_keywords and len(shared_overview_terms) >= 2:
            return (
                f"Both films also emphasize "
                f"{self._format_list(shared_overview_terms[:3])}."
            )

        if semantic_score >= 0.65 and metadata_score >= 0.45:
            return "The semantic and metadata signals both point to a close fit."

        return ""

    def _same_collection(self, selected, recommended, signals):
        if signals.get("same_collection"):
            return True

        selected_collection = self._collection_name(selected.get("collection"))
        recommended_collection = self._collection_name(recommended.get("collection"))

        return (
            bool(selected_collection)
            and selected_collection.casefold() == recommended_collection.casefold()
        )

    def _collection_name(self, raw_collection):
        if self._is_empty(raw_collection):
            return ""

        parsed = self._parse_json(raw_collection)
        if isinstance(parsed, dict):
            raw_collection = parsed.get("name")

        return "" if self._is_empty(raw_collection) else str(raw_collection).strip()

    def _parse_genres(self, raw_genres):
        if self._is_empty(raw_genres):
            return []

        parsed = self._parse_json(raw_genres)
        if isinstance(parsed, list):
            return self._unique_names(
                item.get("name") if isinstance(item, dict) else item
                for item in parsed
            )

        raw_text = str(raw_genres)
        normalized = raw_text.casefold()
        known_names = [
            self._normalize_genre(genre)
            for genre in KNOWN_TMDB_GENRES
            if genre.casefold() in normalized
        ]

        if known_names:
            return self._unique_names(known_names)

        return self._unique_names(
            part.strip()
            for part in re.split(r"[,|;/]+", raw_text)
            if part.strip()
        )

    def _parse_keywords(self, raw_keywords):
        if self._is_empty(raw_keywords):
            return []

        parsed = self._parse_json(raw_keywords)
        if isinstance(parsed, list):
            names = [
                item.get("name") if isinstance(item, dict) else item
                for item in parsed
            ]
            return self._unique_keywords(names)

        text = str(raw_keywords)
        if re.search(r"[,|;/]", text):
            return self._unique_keywords(
                part.strip() for part in re.split(r"[,|;/]+", text)
            )

        return self._unique_keywords(WORD_RE.findall(text.casefold()))

    def _parse_names(self, raw_items):
        if self._is_empty(raw_items):
            return []

        parsed = self._parse_json(raw_items)
        if isinstance(parsed, list):
            return self._unique_names(
                item.get("name") if isinstance(item, dict) else item
                for item in parsed
            )

        return self._split_plain_names(str(raw_items))

    def _parse_directors(self, raw_crew):
        if self._is_empty(raw_crew):
            return []

        parsed = self._parse_json(raw_crew)
        if isinstance(parsed, list):
            return self._unique_names(
                member.get("name")
                for member in parsed
                if isinstance(member, dict) and member.get("job") == "Director"
            )

        return self._split_plain_names(str(raw_crew))

    def _split_plain_names(self, text):
        if not text.strip():
            return []

        if re.search(r"[,|;/]", text):
            return self._unique_names(
                part.strip() for part in re.split(r"[,|;/]+", text)
            )

        return self._unique_names([text.strip()])

    def _shared_overview_terms(self, selected, recommended):
        title_tokens = set(self._word_tokens(self._title(selected)))
        selected_terms = self._overview_terms(selected.get("overview"), title_tokens)
        recommended_terms = set(
            self._overview_terms(recommended.get("overview"), title_tokens)
        )

        return [
            term
            for term in selected_terms
            if term in recommended_terms
        ][:3]

    def _overview_terms(self, overview, extra_stop_words):
        if self._is_empty(overview):
            return []

        terms = []
        seen = set()

        for token in self._word_tokens(overview):
            if (
                len(token) < 4
                or token in OVERVIEW_STOP_WORDS
                or token in extra_stop_words
                or token in seen
            ):
                continue

            seen.add(token)
            terms.append(token)

        return terms

    def _shared(self, selected_values, recommended_values):
        recommended_lookup = {
            self._normalize_key(value): value
            for value in recommended_values
            if value
        }
        shared = []

        for value in selected_values:
            key = self._normalize_key(value)
            if key in recommended_lookup:
                shared.append(value)

        return shared

    def _cache_key(self, selected, recommended, signals):
        selected_id = self._movie_identity(selected)
        recommended_id = self._movie_identity(recommended)
        signal_items = []

        for key in (
            "same_collection",
            "collection",
            "title",
            "keyword",
            "genre",
            "semantic",
            "metadata",
            "metadata_similarity",
        ):
            value = signals.get(key)
            if isinstance(value, bool):
                signal_items.append((key, value))
            elif isinstance(value, (int, float)):
                signal_items.append((key, round(float(value), 3)))
            else:
                signal_items.append((key, str(value)))

        return selected_id, recommended_id, tuple(signal_items)

    def _movie_identity(self, row):
        movie_id = row.get("id")
        if not self._is_empty(movie_id):
            return str(movie_id)

        return self._title(row).casefold()

    def _title(self, row):
        for column in ("original_title", "title"):
            value = row.get(column)
            if not self._is_empty(value):
                return str(value).strip()

        return "this movie"

    def _row_to_dict(self, row):
        if hasattr(row, "to_dict"):
            return row.to_dict()

        if isinstance(row, dict):
            return dict(row)

        return {}

    def _parse_json(self, value):
        if not isinstance(value, str):
            return value

        text = value.strip()
        if not text or text[0] not in "[{":
            return None

        try:
            return json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return None

    def _unique_names(self, values):
        names = []
        seen = set()

        for value in values:
            if self._is_empty(value):
                continue

            name = str(value).strip()
            if not name:
                continue

            key = self._normalize_key(name)
            if key in seen:
                continue

            seen.add(key)
            names.append(name)

        return names

    def _unique_keywords(self, values):
        keywords = []
        seen = set()

        for value in values:
            if self._is_empty(value):
                continue

            keyword = str(value).strip().casefold()
            if (
                not keyword
                or len(keyword) < 3
                or keyword in KEYWORD_STOP_WORDS
            ):
                continue

            key = self._normalize_key(keyword)
            if key in seen:
                continue

            seen.add(key)
            keywords.append(keyword)

        return keywords

    def _normalize_genre(self, genre):
        clean_genre = str(genre).strip()
        return "Sci-Fi" if clean_genre.casefold() == "science fiction" else clean_genre

    def _normalize_key(self, value):
        return " ".join(WORD_RE.findall(str(value).casefold()))

    def _word_tokens(self, text):
        if self._is_empty(text):
            return []

        return [
            token
            for token in WORD_RE.findall(str(text).casefold())
            if token not in TITLE_STOP_WORDS
        ]

    def _format_list(self, values):
        values = [str(value).strip() for value in values if str(value).strip()]

        if not values:
            return ""

        if len(values) == 1:
            return values[0]

        if len(values) == 2:
            return f"{values[0]} and {values[1]}"

        return f"{', '.join(values[:-1])}, and {values[-1]}"

    def _limit_words(self, text, max_words):
        words = text.split()
        if len(words) <= max_words:
            return text

        trimmed = " ".join(words[:max_words]).rstrip(".,;:")
        return f"{trimmed}."

    def _safe_float(self, value):
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        return score if math.isfinite(score) else 0.0

    def _is_empty(self, value):
        if value is None:
            return True

        try:
            return bool(math.isnan(value))
        except (TypeError, ValueError):
            pass

        return False
