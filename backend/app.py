import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

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
