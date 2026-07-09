import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

DATAFRAME_FILE = "dumped_obj/movie_dataframe_for_app.csv"
MOVIE_DATA_FILE = "dumped_obj/movie_data_for_app.csv"


def tmdb_get(endpoint, params=None):
    if params is None:
        params = {}

    params["api_key"] = API_KEY
    params["language"] = "en-US"

    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, params=params)
    response.raise_for_status()

    time.sleep(0.25)
    return response.json()


def fetch_movie_details(movie_id):
    details = tmdb_get(f"/movie/{movie_id}")
    credits = tmdb_get(f"/movie/{movie_id}/credits")
    keywords = tmdb_get(f"/movie/{movie_id}/keywords")

    director = ""
    for person in credits.get("crew", []):
        if person.get("job") == "Director":
            director = person.get("name", "")
            break

    cast = " ".join([
        person.get("name", "")
        for person in credits.get("cast", [])[:5]
    ])

    crew = director

    genres = " ".join([
        genre.get("name", "")
        for genre in details.get("genres", [])
    ])

    keyword_text = " ".join([
        keyword.get("name", "")
        for keyword in keywords.get("keywords", [])
    ])

    production_companies = " ".join([
        company.get("name", "")
        for company in details.get("production_companies", [])
    ])

    spoken_languages = " ".join([
        lang.get("english_name", "")
        for lang in details.get("spoken_languages", [])
    ])

    return {
        "budget": details.get("budget", 0),
        "genres": genres,
        "id": details.get("id"),
        "keywords": keyword_text,
        "original_language": details.get("original_language", ""),
        "original_title": details.get("title", ""),
        "overview": details.get("overview", ""),
        "popularity": details.get("popularity", 0),
        "production_companies": production_companies,
        "release_date": details.get("release_date", ""),
        "revenue": details.get("revenue", 0),
        "runtime": details.get("runtime", 0),
        "spoken_languages": spoken_languages,
        "tagline": details.get("tagline", ""),
        "vote_average": details.get("vote_average", 0),
        "vote_count": details.get("vote_count", 0),
        "cast": cast,
        "crew": crew,
        "weighted_avg": 0,
        "weighted_avg_scaled": 0,
        "popularity_scaled": 0,
        "score_mix": 0,
    }


def fetch_source_movies():
    movie_ids = set()

    sources = [
        "/movie/popular",
        "/movie/now_playing",
        "/movie/upcoming",
        "/movie/top_rated",
    ]

    for source in sources:
        for page in range(1, 3):
            data = tmdb_get(source, {"page": page})
            for movie in data.get("results", []):
                movie_ids.add(movie["id"])

    return list(movie_ids)


def main():
    old_df = pd.read_csv(DATAFRAME_FILE)
    existing_ids = set(old_df["id"].astype(int).tolist())

    movie_ids = fetch_source_movies()

    new_movies = []

    for movie_id in movie_ids:
        if movie_id in existing_ids:
            continue

        try:
            movie = fetch_movie_details(movie_id)
            new_movies.append(movie)
            print("Added:", movie["original_title"])
        except Exception as e:
            print("Skipped:", movie_id, e)

    if not new_movies:
        print("No new movies found.")
        return

    new_df = pd.DataFrame(new_movies)

    combined_df = pd.concat(
        [old_df.drop(columns=["index"], errors="ignore"), new_df],
        ignore_index=True
    )

    combined_df = combined_df.drop_duplicates(subset=["id"], keep="first")
    combined_df.insert(0, "index", range(len(combined_df)))

    combined_df.to_csv(DATAFRAME_FILE, index=False)

    movie_data_df = combined_df.drop(columns=["index"], errors="ignore")
    movie_data_df.to_csv(MOVIE_DATA_FILE, index=False)

    print("Old size:", old_df.shape)
    print("New movies added:", len(new_movies))
    print("Updated size:", combined_df.shape)


if __name__ == "__main__":
    main()