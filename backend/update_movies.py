import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

OLD_FILE = "dumped_obj/movie_dataframe_for_app.csv"
TEST_OUTPUT = "dumped_obj/movie_dataframe_updated_TEST.csv"


def get_popular_movies(page):
    url = f"{BASE_URL}/movie/popular"
    params = {
        "api_key": API_KEY,
        "language": "en-US",
        "page": page
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("results", [])


old_df = pd.read_csv(OLD_FILE)

print("Old dataset size:", old_df.shape)

new_movies = []

for page in range(1, 6):
    movies = get_popular_movies(page)

    for movie in movies:
        new_movies.append({
            "index": None,
            "budget": 0,
            "genres": "",
            "id": movie.get("id"),
            "keywords": "",
            "original_language": movie.get("original_language", ""),
            "original_title": movie.get("original_title", ""),
            "overview": movie.get("overview", ""),
            "popularity": movie.get("popularity", 0),
            "production_companies": "",
            "release_date": movie.get("release_date", ""),
            "revenue": 0,
            "runtime": 0,
            "spoken_languages": "",
            "tagline": "",
            "vote_average": movie.get("vote_average", 0),
            "vote_count": movie.get("vote_count", 0),
            "cast": "",
            "crew": "",
            "weighted_avg": 0,
            "weighted_avg_scaled": 0,
            "popularity_scaled": 0,
            "score_mix": 0
        })

new_df = pd.DataFrame(new_movies)

combined_df = pd.concat([old_df, new_df], ignore_index=True)
combined_df = combined_df.drop_duplicates(subset=["id"], keep="first")
combined_df["index"] = range(len(combined_df))

combined_df.to_csv(TEST_OUTPUT, index=False)

print("New movies fetched:", len(new_df))
print("Updated dataset size:", combined_df.shape)
print("Saved test file:", TEST_OUTPUT)