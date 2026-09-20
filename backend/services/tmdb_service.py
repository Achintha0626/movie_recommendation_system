import os
import time
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"


class TMDBNotFoundError(Exception):
    pass


class TMDBRequestError(Exception):

    def __init__(self, status_code, endpoint):
        super().__init__(f"TMDB request failed ({status_code}) for {endpoint}")
        self.status_code = status_code
        self.endpoint = endpoint


class TMDBService:

    def __init__(self):
        self.api_key = API_KEY

        self.session = requests.Session()

        self.last_sync_stats = {
            "checked": 0,
            "skipped": 0,
            "start_date": None,
            "end_date": None,
        }

    def get(self, endpoint, params=None):

        if params is None:
            params = {}

        params["api_key"] = self.api_key
        params["language"] = "en-US"

        url = f"{BASE_URL}{endpoint}"

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=20,
            )
        except requests.RequestException:
            raise TMDBRequestError("request", endpoint) from None

        if response.status_code == 404:
            raise TMDBNotFoundError()

        try:
            response.raise_for_status()
        except requests.HTTPError:
            raise TMDBRequestError(response.status_code, endpoint) from None

        return response.json()

    def _coerce_date(self, value):
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        return datetime.fromisoformat(str(value)).date()

    def _change_date_range(self, start_date=None, end_date=None):
        if end_date is None:
            end = date.today()
        else:
            end = self._coerce_date(end_date)

        if start_date is None:
            start = end - timedelta(days=7)
        else:
            start = self._coerce_date(start_date)

        return start.isoformat(), end.isoformat()

    def sync_changed_movies(self, start_date=None, end_date=None):
        start_date, end_date = self._change_date_range(start_date, end_date)

        processed_ids = set()
        movies = []
        skipped = 0
        page = 1
        total_pages = 1

        while page <= total_pages:
            try:
                data = self.get(
                    "/movie/changes",
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "page": page,
                    }
                )
            except TMDBNotFoundError:
                skipped += 1
                print(f"Skipped TMDB changes page: {page} (404 error)")
                page += 1
                continue
            except TMDBRequestError as e:
                skipped += 1
                print(
                    f"Skipped TMDB changes page: {page} "
                    f"({e.status_code} error)"
                )
                page += 1
                continue

            total_pages = data.get("total_pages", 1) or 1

            print(
                f"Processing TMDB changes page "
                f"{page}/{total_pages}"
            )

            for item in data.get("results", []):
                movie_id = item.get("id")

                if movie_id is None:
                    skipped += 1
                    continue

                if movie_id in processed_ids:
                    continue

                processed_ids.add(movie_id)

                try:
                    movies.append(
                        self.fetch_movie_details(movie_id)
                    )

                except TMDBNotFoundError:
                    skipped += 1
                    print(f"Skipped missing movie: {movie_id}")

                except TMDBRequestError as e:
                    skipped += 1
                    print(
                        f"Skipped movie: {movie_id} "
                        f"({e.status_code} error)"
                    )

                except Exception as e:
                    skipped += 1
                    print(
                        f"Skipped movie: {movie_id} "
                        f"({type(e).__name__})"
                    )

            page += 1

        self.last_sync_stats = {
            "checked": len(processed_ids),
            "skipped": skipped,
            "start_date": start_date,
            "end_date": end_date,
        }

        return movies

    def fetch_movie_details(self, movie_id):

        # One TMDB request instead of three separate requests.
        details = self.get(
            f"/movie/{movie_id}",
            {
                "append_to_response": "credits,keywords"
            }
        )

        credits = details.get("credits", {})
        keywords = details.get("keywords", {})

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
            for company in details.get(
                "production_companies",
                []
            )
        ])

        spoken_languages = " ".join([
            lang.get("english_name", "")
            for lang in details.get(
                "spoken_languages",
                []
            )
        ])

        return {
            "budget": details.get("budget", 0),
            "genres": genres,
            "id": details.get("id"),
            "keywords": keyword_text,
            "original_language": details.get(
                "original_language",
                ""
            ),
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

    def fetch_source_movies(self):
        movie_ids = set()

        sources = [
            "/movie/popular",
            "/movie/now_playing",
            "/movie/upcoming",
            "/movie/top_rated",
        ]

        for source in sources:
            for page in range(1, 3):
                data = self.get(
                    source,
                    {
                        "page": page
                    }
                )

                for movie in data.get("results", []):
                    movie_ids.add(movie["id"])

        return list(movie_ids)