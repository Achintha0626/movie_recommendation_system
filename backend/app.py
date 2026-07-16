import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.explanation_service import ExplanationService
from services.hybrid_ranking_service import HybridRankingService
from services.semantic_similarity_service import SemanticSimilarityService


BASE_DIR = Path(__file__).resolve().parent
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_TRENDING_URL = "https://api.themoviedb.org/3/trending/movie/day"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_ORIGINAL_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

load_dotenv(BASE_DIR / ".env")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip().rstrip("/")

allowed_origins = [FRONTEND_URL] if FRONTEND_URL else []

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data = pd.read_csv(BASE_DIR / "dumped_obj" / "movie_data_for_app.csv")
dataframe = pd.read_csv(BASE_DIR / "dumped_obj" / "movie_dataframe_for_app.csv")
sig = joblib.load(BASE_DIR / "dumped_obj" / "sigmoid_kernel.pkl")
semantic_similarity_service = SemanticSimilarityService(dataframe)
hybrid_ranking_service = HybridRankingService(
    dataframe,
    sig,
    semantic_similarity_service,
)
explanation_service = ExplanationService()

indices = pd.Series(data.index, index=data["original_title"]).drop_duplicates()
movie_titles = list(dict.fromkeys(data["original_title"].dropna().astype(str)))

DEFAULT_GENRES = [
    "All",
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Drama",
    "Fantasy",
    "Horror",
    "Romance",
    "Sci-Fi",
    "Thriller",
]

MATCH_SCORE_MIN_PERCENT = 55
MATCH_SCORE_MAX_PERCENT = 99
CONTENT_SIMILARITY_WEIGHT = 0.60
GENRE_OVERLAP_WEIGHT = 0.15
KEYWORD_OVERLAP_WEIGHT = 0.15
POPULARITY_RATING_WEIGHT = 0.10
FRANCHISE_TITLE_BOOST = 0.20
TITLE_STOP_WORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "world",
    "movie",
    "part",
    "to",
    "in",
    "on",
    "at",
    "for",
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


def _word_tokens(text) -> tuple[str, ...]:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ()

    return tuple(WORD_RE.findall(str(text).casefold()))


def _important_title_tokens(title) -> frozenset[str]:
    return frozenset(
        token
        for token in _word_tokens(title)
        if len(token) > 1 and token not in TITLE_STOP_WORDS
    )


def _normalize_movie_genre(name: str) -> str:
    clean_name = name.strip()
    return "Sci-Fi" if clean_name.casefold() == "science fiction" else clean_name


def _parse_plain_genres(raw_genres: str) -> tuple[str, ...]:
    normalized = raw_genres.casefold()
    names = [
        _normalize_movie_genre(genre)
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


def _parse_genres(raw_genres) -> tuple[str, ...]:
    """Convert the dataset's serialized TMDB genre objects into clean names."""
    if raw_genres is None or (isinstance(raw_genres, float) and pd.isna(raw_genres)):
        return ()

    try:
        genres = json.loads(raw_genres) if isinstance(raw_genres, str) else raw_genres
    except (json.JSONDecodeError, TypeError):
        return _parse_plain_genres(raw_genres) if isinstance(raw_genres, str) else ()

    if not isinstance(genres, list):
        return _parse_plain_genres(raw_genres) if isinstance(raw_genres, str) else ()

    names = []
    for genre in genres:
        name = genre.get("name") if isinstance(genre, dict) else genre
        if not isinstance(name, str) or not name.strip():
            continue

        names.append(_normalize_movie_genre(name))

    return tuple(dict.fromkeys(names))


movie_genres = dataframe["genres"].apply(_parse_genres)
movie_genre_keys = movie_genres.apply(
    lambda genres: frozenset(genre.casefold() for genre in genres)
)


def _parse_names(raw_items, split_plain_text: bool = False) -> frozenset[str]:
    """Extract normalized names from serialized keywords or cast data."""
    if raw_items is None or (isinstance(raw_items, float) and pd.isna(raw_items)):
        return frozenset()

    try:
        items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
    except (json.JSONDecodeError, TypeError):
        if not isinstance(raw_items, str) or not raw_items.strip():
            return frozenset()

        if split_plain_text:
            return frozenset(_word_tokens(raw_items))

        return frozenset({raw_items.strip().casefold()})

    if not isinstance(items, list):
        if isinstance(raw_items, str) and raw_items.strip():
            return (
                frozenset(_word_tokens(raw_items))
                if split_plain_text
                else frozenset({raw_items.strip().casefold()})
            )

        return frozenset()

    return frozenset(
        name.strip().casefold()
        for item in items
        if isinstance(item, dict)
        and isinstance((name := item.get("name")), str)
        and name.strip()
    )


def _parse_directors(raw_crew) -> frozenset[str]:
    """Extract normalized director names from serialized crew data."""
    if raw_crew is None or (isinstance(raw_crew, float) and pd.isna(raw_crew)):
        return frozenset()

    try:
        crew = json.loads(raw_crew) if isinstance(raw_crew, str) else raw_crew
    except (json.JSONDecodeError, TypeError):
        if isinstance(raw_crew, str) and raw_crew.strip():
            return frozenset({raw_crew.strip().casefold()})

        return frozenset()

    if not isinstance(crew, list):
        if isinstance(raw_crew, str) and raw_crew.strip():
            return frozenset({raw_crew.strip().casefold()})

        return frozenset()

    return frozenset(
        member["name"].strip().casefold()
        for member in crew
        if isinstance(member, dict)
        and member.get("job") == "Director"
        and isinstance(member.get("name"), str)
        and member["name"].strip()
    )


movie_keywords = dataframe["keywords"].apply(
    lambda keywords: _parse_names(keywords, split_plain_text=True)
)
movie_cast = dataframe["cast"].apply(_parse_names)
movie_directors = dataframe["crew"].apply(_parse_directors)
movie_title_tokens = dataframe["original_title"].apply(_important_title_tokens)
dataset_genres = {genre for genres in movie_genres for genre in genres}

if dataset_genres:
    preferred_genres = [
        genre for genre in DEFAULT_GENRES[1:] if genre in dataset_genres
    ]
    additional_genres = sorted(
        dataset_genres.difference(preferred_genres), key=str.casefold
    )
    available_genres = ["All", *preferred_genres, *additional_genres]
else:
    available_genres = DEFAULT_GENRES


def _finite_similarity_score(similarity_score) -> float | None:
    try:
        score = float(similarity_score)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(score):
        return None

    return score


def _clamped_score(score) -> float:
    finite_score = _finite_similarity_score(score)
    if finite_score is None:
        return 0.0

    return max(0.0, min(1.0, finite_score))


def _numeric_series(column_name: str) -> pd.Series:
    if column_name not in dataframe:
        return pd.Series([0.0] * len(dataframe), index=dataframe.index)

    return pd.to_numeric(dataframe[column_name], errors="coerce").fillna(0.0)


def _normalize_series(series: pd.Series) -> pd.Series:
    finite_series = pd.to_numeric(series, errors="coerce").fillna(0.0)
    min_value = finite_series.min()
    max_value = finite_series.max()

    if max_value <= min_value:
        return pd.Series([0.0] * len(finite_series), index=finite_series.index)

    return (finite_series - min_value) / (max_value - min_value)


popularity_score = _normalize_series(_numeric_series("popularity"))
rating_score = (_numeric_series("vote_average") / 10).clip(0.0, 1.0)
vote_count_score = _normalize_series(_numeric_series("vote_count").apply(math.log1p))
movie_popularity_rating_score = (
    (popularity_score * 0.45) +
    (rating_score * 0.35) +
    (vote_count_score * 0.20)
).clip(0.0, 1.0)


def _selected_overlap_score(selected_values, candidate_values) -> float:
    if not selected_values or not candidate_values:
        return 0.0

    return len(selected_values & candidate_values) / len(selected_values)


def _keyword_overlap_score(selected_keywords, candidate_keywords) -> float:
    if not selected_keywords or not candidate_keywords:
        return 0.0

    shared_count = len(selected_keywords & candidate_keywords)
    if shared_count == 0:
        return 0.0

    return min(1.0, shared_count / min(len(selected_keywords), 6))


def _title_overlap_score(selected_index: int, recommended_index: int) -> float:
    selected_tokens = movie_title_tokens.iloc[selected_index]
    recommended_tokens = movie_title_tokens.iloc[recommended_index]

    return _selected_overlap_score(selected_tokens, recommended_tokens)


def _hybrid_score_parts(
    selected_index: int,
    recommended_index: int,
    similarity_score,
) -> dict[str, float]:
    genre_score = _selected_overlap_score(
        movie_genre_keys.iloc[selected_index],
        movie_genre_keys.iloc[recommended_index],
    )
    keyword_score = _keyword_overlap_score(
        movie_keywords.iloc[selected_index],
        movie_keywords.iloc[recommended_index],
    )
    content_score = _clamped_score(similarity_score)
    popularity_rating = float(movie_popularity_rating_score.iloc[recommended_index])
    title_score = _title_overlap_score(selected_index, recommended_index)
    base_score = (
        (CONTENT_SIMILARITY_WEIGHT * content_score) +
        (GENRE_OVERLAP_WEIGHT * genre_score) +
        (KEYWORD_OVERLAP_WEIGHT * keyword_score) +
        (POPULARITY_RATING_WEIGHT * popularity_rating)
    )

    return {
        "content": content_score,
        "genre": genre_score,
        "keyword": keyword_score,
        "popularity_rating": popularity_rating,
        "title": title_score,
        "hybrid": min(1.0, base_score + (FRANCHISE_TITLE_BOOST * title_score)),
    }


def _raw_match_percentage(similarity_score) -> int:
    score = _finite_similarity_score(similarity_score)
    if score is None:
        score = 0.0

    return int(round(max(0.0, min(1.0, score)) * 100))


def _match_percentage(similarity_score, comparison_scores=None) -> int:
    score = _finite_similarity_score(similarity_score)
    if score is None:
        return 0

    if comparison_scores is not None:
        finite_scores = [
            finite_score
            for candidate_score in comparison_scores
            if (finite_score := _finite_similarity_score(candidate_score)) is not None
        ]

        if finite_scores:
            min_score = min(finite_scores)
            max_score = max(finite_scores)

            if max_score > min_score:
                normalized_score = (score - min_score) / (max_score - min_score)
                normalized_score = max(0.0, min(1.0, normalized_score))
                return int(
                    round(
                        MATCH_SCORE_MIN_PERCENT
                        + normalized_score
                        * (MATCH_SCORE_MAX_PERCENT - MATCH_SCORE_MIN_PERCENT)
                    )
                )

    return _raw_match_percentage(score)


def _recommendation_reasons(
    selected_index: int,
    recommended_index: int,
    similarity_score,
    score_parts: dict[str, float] | None = None,
) -> list[str]:
    if score_parts is None:
        score_parts = _hybrid_score_parts(
            selected_index,
            recommended_index,
            similarity_score,
        )

    reasons = []

    if score_parts["title"] > 0:
        reasons.append("Same franchise / similar title")

    if score_parts["genre"] > 0:
        reasons.append("Similar genre")

    if score_parts["keyword"] > 0:
        reasons.append("Similar keywords")

    if movie_cast.iloc[selected_index] & movie_cast.iloc[recommended_index]:
        reasons.append("Shared cast")

    if movie_directors.iloc[selected_index] & movie_directors.iloc[recommended_index]:
        reasons.append("Same director")

    if score_parts["popularity_rating"] >= 0.60:
        reasons.append("Popular/high-rated movie")

    if score_parts["content"] >= 0.70:
        reasons.append("Similar story overview")

    return reasons or ["Similar story overview"]


def _movie_fallback(title: str) -> dict:
    """Return a complete card payload when TMDB metadata is unavailable."""
    return {
        "id": None,
        "title": title,
        "poster_url": None,
        "release_date": "",
        "vote_average": None,
        "overview": "",
    }


@lru_cache(maxsize=512)
def search_tmdb_movie(title: str) -> dict:
    """Find the closest TMDB movie without allowing lookup failures to escape."""
    fallback = _movie_fallback(title)

    if not TMDB_API_KEY or TMDB_API_KEY == "your_key_here":
        return fallback

    try:
        response = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": TMDB_API_KEY, "query": title},
            timeout=5,
        )
        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            return fallback

        movie = results[0]
        poster_path = movie.get("poster_path")

        return {
            "id": movie.get("id"),
            "title": movie.get("title") or title,
            "poster_url": (
                f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None
            ),
            "release_date": movie.get("release_date") or "",
            "vote_average": movie.get("vote_average"),
            "overview": movie.get("overview") or "",
        }
    except (
        requests.RequestException,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
    ):
        return fallback


def _tmdb_image_url(path: str | None, original: bool = False) -> str | None:
    if not path:
        return None

    base_url = TMDB_ORIGINAL_IMAGE_BASE_URL if original else TMDB_IMAGE_BASE_URL
    return f"{base_url}{path}"


@lru_cache(maxsize=256)
def get_tmdb_movie_details(tmdb_id: int) -> dict:
    """Fetch and normalize the details needed by the movie details page."""
    if not TMDB_API_KEY or TMDB_API_KEY == "your_key_here":
        raise HTTPException(
            status_code=503,
            detail="TMDB API key is not configured on the backend.",
        )

    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            params={
                "api_key": TMDB_API_KEY,
                "append_to_response": "credits,videos",
            },
            timeout=8,
        )
        response.raise_for_status()
        movie = response.json()

        credits = movie.get("credits") or {}
        crew = credits.get("crew") or []
        cast_members = credits.get("cast") or []
        videos = (movie.get("videos") or {}).get("results") or []

        director = next(
            (
                member.get("name")
                for member in crew
                if member.get("job") == "Director" and member.get("name")
            ),
            None,
        )

        trailer = next(
            (
                video
                for video in videos
                if video.get("site") == "YouTube"
                and video.get("type") == "Trailer"
                and video.get("key")
            ),
            None,
        )

        cast = [
            {
                "name": member.get("name") or "Unknown",
                "character": member.get("character") or "",
                "profile_url": _tmdb_image_url(member.get("profile_path")),
            }
            for member in cast_members[:6]
        ]

        return {
            "id": movie.get("id") or tmdb_id,
            "title": movie.get("title") or "Untitled",
            "poster_url": _tmdb_image_url(movie.get("poster_path")),
            "backdrop_url": _tmdb_image_url(
                movie.get("backdrop_path"), original=True
            ),
            "release_date": movie.get("release_date") or "",
            "runtime": movie.get("runtime"),
            "vote_average": movie.get("vote_average"),
            "overview": movie.get("overview") or "",
            "genres": [
                genre.get("name")
                for genre in (movie.get("genres") or [])
                if genre.get("name")
            ],
            "director": director,
            "cast": cast,
            "trailer_url": (
                f"https://www.youtube.com/watch?v={trailer['key']}"
                if trailer
                else None
            ),
        }
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code == 404:
            raise HTTPException(status_code=404, detail="Movie not found on TMDB.") from exc
        raise HTTPException(
            status_code=502,
            detail="TMDB could not provide movie details right now.",
        ) from exc
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch movie details from TMDB.",
        ) from exc


@app.get("/movies")
def get_movies():
    return movie_titles


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/search")
def search_movies(query: str = ""):
    normalized_query = query.strip().casefold()

    if not normalized_query:
        return {"results": []}

    prefix_matches = []
    partial_matches = []

    for title in movie_titles:
        normalized_title = title.casefold()

        if normalized_title.startswith(normalized_query):
            prefix_matches.append(title)
        elif normalized_query in normalized_title:
            partial_matches.append(title)

        if len(prefix_matches) >= 10:
            break

    results = (prefix_matches + partial_matches)[:10]
    return {"results": results}


@app.get("/genres")
def get_genres():
    return {"genres": available_genres}


@app.get("/trending")
def trending_movies():
    if not TMDB_API_KEY or TMDB_API_KEY == "your_key_here":
        raise HTTPException(
            status_code=503,
            detail="TMDB API key is not configured on the backend.",
        )

    try:
        response = requests.get(
            TMDB_TRENDING_URL,
            params={"api_key": TMDB_API_KEY},
            timeout=8,
        )
        response.raise_for_status()
        movies = response.json().get("results") or []

        results = [
            {
                "id": movie.get("id"),
                "title": (
                    movie.get("title")
                    or movie.get("original_title")
                    or "Untitled"
                ),
                "poster_url": _tmdb_image_url(movie.get("poster_path")),
                "backdrop_url": _tmdb_image_url(
                    movie.get("backdrop_path"), original=True
                ),
                "release_date": movie.get("release_date") or "",
                "vote_average": movie.get("vote_average"),
                "overview": movie.get("overview") or "",
            }
            for movie in movies[:12]
        ]
        return {"results": results}
    except requests.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="TMDB could not provide trending movies right now.",
        ) from exc
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch trending movies from TMDB.",
        ) from exc


@app.get("/recommend/{movie_title}")
def recommend(movie_title: str, genre: str | None = None):
    if movie_title not in indices:
        return {"error": "Movie not found"}

    idx = int(indices[movie_title])

    requested_genre = (genre or "All").strip()
    normalized_genre = requested_genre.casefold()
    genre_filter = None

    if normalized_genre and normalized_genre != "all":
        genre_lookup = {
            available_genre.casefold(): available_genre
            for available_genre in available_genres[1:]
        }
        canonical_genre = genre_lookup.get(normalized_genre)

        if canonical_genre is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown genre: {requested_genre}",
            )

        genre_filter = canonical_genre

    candidates = hybrid_ranking_service.recommend(
        idx,
        genre_filter=genre_filter,
        limit=10,
    )
    recommendation_titles = [candidate["title"] for candidate in candidates]

    # The ranking logic above remains local; only metadata lookup is parallelized.
    with ThreadPoolExecutor(max_workers=5) as executor:
        enriched_movies = list(executor.map(search_tmdb_movie, recommendation_titles))

    recommendations = []
    selected_movie = dataframe.iloc[idx]

    for movie, candidate in zip(enriched_movies, candidates):
        recommended_movie = dataframe.iloc[candidate["index"]]
        recommendations.append({
            **movie,
            "match_score": candidate["match_score"],
            "reasons": candidate["reasons"],
            "explanation": explanation_service.explain(
                selected_movie,
                recommended_movie,
                candidate.get("parts", {}),
            ),
        })

    return {"movie": movie_title, "recommendations": recommendations}


@app.get("/movie/{tmdb_id}")
def movie_details(tmdb_id: int):
    return get_tmdb_movie_details(tmdb_id)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
