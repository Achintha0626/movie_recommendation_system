import os
import sys


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from services.dataset_service import DatasetService
from services.tmdb_service import TMDBNotFoundError, TMDBService


TMDB_SOURCES = [
    ("/movie/popular", 3),
    ("/movie/top_rated", 2),
    ("/movie/upcoming", 2),
    ("/movie/now_playing", 2),
]


def main():
    tmdb = TMDBService()
    dataset = DatasetService()

    existing_df = dataset.load_dataframe()
    existing_ids = build_existing_ids(existing_df)
    candidate_ids = fetch_candidate_ids(tmdb)
    new_candidate_ids = [
        movie_id for movie_id in candidate_ids if movie_id not in existing_ids
    ]
    new_movies = fetch_new_movies(tmdb, new_candidate_ids)

    print("Existing movies:", len(existing_df))
    print("Candidate IDs:", len(candidate_ids))
    print("New movies:", len(new_movies))

    if not new_movies:
        print("Final movie count:", len(existing_df))
        print("No new movies found.")
        return 0

    updated_df = dataset.update(existing_df, new_movies)

    print("Final movie count:", len(updated_df))
    return 0


def build_existing_ids(df):
    return {
        coerced_id
        for movie_id in df["id"].dropna().tolist()
        if (coerced_id := coerce_movie_id(movie_id)) is not None
    }


def fetch_candidate_ids(tmdb):
    candidate_ids = []
    seen_ids = set()

    for endpoint, pages in TMDB_SOURCES:
        for page in range(1, pages + 1):
            data = tmdb.get(endpoint, {"page": page})

            for movie in data.get("results", []):
                movie_id = movie.get("id")

                if movie_id is None:
                    continue

                movie_id = coerce_movie_id(movie_id)

                if movie_id is None:
                    continue

                if movie_id in seen_ids:
                    continue

                seen_ids.add(movie_id)
                candidate_ids.append(movie_id)

    return candidate_ids


def fetch_new_movies(tmdb, movie_ids):
    movies = []

    for movie_id in movie_ids:
        try:
            movies.append(tmdb.fetch_movie_details(movie_id))
        except TMDBNotFoundError:
            continue

    return movies


def coerce_movie_id(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
