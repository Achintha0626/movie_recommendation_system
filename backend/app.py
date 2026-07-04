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
    return data["original_title"].dropna().tolist()


@app.get("/recommend/{movie_title}")
def recommend(movie_title: str):
    if movie_title not in indices:
        return {"error": "Movie not found"}

    idx = indices[movie_title]
    scores = list(enumerate(sig[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:11]
    movie_indices = [i[0] for i in scores]

    recommendation_titles = (
        dataframe["original_title"].iloc[movie_indices].dropna().tolist()
    )

    # The ranking logic above remains local; only metadata lookup is parallelized.
    with ThreadPoolExecutor(max_workers=5) as executor:
        recommendations = list(executor.map(search_tmdb_movie, recommendation_titles))

    return {"movie": movie_title, "recommendations": recommendations}


@app.get("/movie/{tmdb_id}")
def movie_details(tmdb_id: int):
    return get_tmdb_movie_details(tmdb_id)
