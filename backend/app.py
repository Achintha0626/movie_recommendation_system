import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_TRENDING_URL = "https://api.themoviedb.org/3/trending/movie/day"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_ORIGINAL_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

load_dotenv(BASE_DIR / ".env")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

data = pd.read_csv(BASE_DIR / "dumped_obj" / "movie_data_for_app.csv")
dataframe = pd.read_csv(BASE_DIR / "dumped_obj" / "movie_dataframe_for_app.csv")
sig = joblib.load(BASE_DIR / "dumped_obj" / "sigmoid_kernel.pkl")

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


def _parse_genres(raw_genres) -> tuple[str, ...]:
    """Convert the dataset's serialized TMDB genre objects into clean names."""
    if raw_genres is None or (isinstance(raw_genres, float) and pd.isna(raw_genres)):
        return ()

    try:
        genres = json.loads(raw_genres) if isinstance(raw_genres, str) else raw_genres
    except (json.JSONDecodeError, TypeError):
        return ()

    if not isinstance(genres, list):
        return ()

    names = []
    for genre in genres:
        name = genre.get("name") if isinstance(genre, dict) else genre
        if not isinstance(name, str) or not name.strip():
            continue

        clean_name = "Sci-Fi" if name.strip().casefold() == "science fiction" else name.strip()
        names.append(clean_name)

    return tuple(dict.fromkeys(names))


movie_genres = dataframe["genres"].apply(_parse_genres)
movie_genre_keys = movie_genres.apply(
    lambda genres: frozenset(genre.casefold() for genre in genres)
)


def _parse_names(raw_items) -> frozenset[str]:
    """Extract normalized names from serialized keywords or cast data."""
    if raw_items is None or (isinstance(raw_items, float) and pd.isna(raw_items)):
        return frozenset()

    try:
        items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
    except (json.JSONDecodeError, TypeError):
        return frozenset()

    if not isinstance(items, list):
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
        return frozenset()

    if not isinstance(crew, list):
        return frozenset()

    return frozenset(
        member["name"].strip().casefold()
        for member in crew
        if isinstance(member, dict)
        and member.get("job") == "Director"
        and isinstance(member.get("name"), str)
        and member["name"].strip()
    )


movie_keywords = dataframe["keywords"].apply(_parse_names)
movie_cast = dataframe["cast"].apply(_parse_names)
movie_directors = dataframe["crew"].apply(_parse_directors)
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


def _match_percentage(similarity_score) -> int:
    try:
        score = float(similarity_score)
    except (TypeError, ValueError):
        score = 0.0

    if not math.isfinite(score):
        score = 0.0

    return int(round(max(0.0, min(1.0, score)) * 100))


def _recommendation_reasons(
    selected_index: int,
    recommended_index: int,
    similarity_score,
) -> list[str]:
    reasons = []

    if _match_percentage(similarity_score) >= 70:
        reasons.append("Similar story overview")

    if movie_genre_keys.iloc[selected_index] & movie_genre_keys.iloc[recommended_index]:
        reasons.append("Similar genre")

    if movie_keywords.iloc[selected_index] & movie_keywords.iloc[recommended_index]:
        reasons.append("Similar keywords")

    if movie_cast.iloc[selected_index] & movie_cast.iloc[recommended_index]:
        reasons.append("Shared cast")

    if movie_directors.iloc[selected_index] & movie_directors.iloc[recommended_index]:
        reasons.append("Same director")

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
    ranked_scores = list(enumerate(sig[idx]))
    ranked_scores = sorted(
        ranked_scores, key=lambda item: item[1], reverse=True
    )[1:11]

    requested_genre = (genre or "All").strip()
    normalized_genre = requested_genre.casefold()

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

        ranked_scores = [
            (movie_index, similarity_score)
            for movie_index, similarity_score in ranked_scores
            if any(
                movie_genre.casefold() == canonical_genre.casefold()
                for movie_genre in movie_genres.iloc[movie_index]
            )
        ]

    candidates = [
        (movie_index, similarity_score, dataframe["original_title"].iloc[movie_index])
        for movie_index, similarity_score in ranked_scores
        if pd.notna(dataframe["original_title"].iloc[movie_index])
    ]
    recommendation_titles = [candidate[2] for candidate in candidates]

    # The ranking logic above remains local; only metadata lookup is parallelized.
    with ThreadPoolExecutor(max_workers=5) as executor:
        enriched_movies = list(executor.map(search_tmdb_movie, recommendation_titles))

    recommendations = [
        {
            **movie,
            "match_score": _match_percentage(similarity_score),
            "reasons": _recommendation_reasons(
                idx, movie_index, similarity_score
            ),
        }
        for movie, (movie_index, similarity_score, _) in zip(
            enriched_movies, candidates
        )
    ]

    return {"movie": movie_title, "recommendations": recommendations}


@app.get("/movie/{tmdb_id}")
def movie_details(tmdb_id: int):
    return get_tmdb_movie_details(tmdb_id)
