import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from services.dataset_service import DatasetService
from services.similarity_service import SimilarityService
from services.tmdb_service import TMDBNotFoundError, TMDBRequestError, TMDBService


BATCH_SIZE = 20
DISCOVER_ENDPOINT = "/discover/movie"
SEARCH_ENDPOINT = "/search/movie"
SEARCH_PAGES = 5

DECADES = [
    (1960, 1969),
    (1970, 1979),
    (1980, 1989),
    (1990, 1999),
    (2000, 2009),
    (2010, 2019),
    (2020, date.today().year),
]

GENRES = [
    ("Action", 28),
    ("Adventure", 12),
    ("Animation", 16),
    ("Comedy", 35),
    ("Crime", 80),
    ("Drama", 18),
    ("Family", 10751),
    ("Fantasy", 14),
    ("History", 36),
    ("Horror", 27),
    ("Music", 10402),
    ("Mystery", 9648),
    ("Romance", 10749),
    ("Science Fiction", 878),
    ("Thriller", 53),
    ("War", 10752),
    ("Western", 37),
]

EXCLUDED_CONTENT_MARKERS = (
    "behind the scenes",
    "behind-the-scenes",
    "documentary",
    "fan film",
    "fan-film",
    "live event",
    "live-event",
    "making of",
    "making-of",
    "rifftrax",
    "short film",
    "short subject",
    "story development",
)


@dataclass
class Candidate:
    movie_id: int
    source: str
    metadata: dict = field(default_factory=dict)
    collection_id: int = None
    collection_name: str = ""
    genre_name: str = ""


class CatalogueSource:
    name = "catalogue"

    def discover(self, tmdb, detail_cache):
        raise NotImplementedError


class OfficialCollectionSource(CatalogueSource):
    name = "official_collection"

    def __init__(self, collection_ids, movie_ids):
        self.collection_ids = collection_ids
        self.movie_ids = movie_ids

    def discover(self, tmdb, detail_cache):
        candidates = []

        for collection_id in self.collection_ids:
            candidates.extend(fetch_collection_candidates(tmdb, collection_id))

        for movie_id in self.movie_ids:
            try:
                details = fetch_movie_summary(tmdb, movie_id, detail_cache)
            except (TMDBNotFoundError, TMDBRequestError):
                continue

            collection = details.get("belongs_to_collection") or {}
            collection_id = collection.get("id")

            if collection_id:
                candidates.extend(fetch_collection_candidates(tmdb, collection_id))
            else:
                candidates.append(
                    Candidate(
                        movie_id=movie_id,
                        source=self.name,
                        metadata=details,
                    )
                )

        return candidates


class FranchiseSearchSource(CatalogueSource):
    name = "franchise_search"

    def __init__(self, search_queries):
        self.search_queries = search_queries

    def discover(self, tmdb, detail_cache):
        candidates = []

        for query in self.search_queries:
            for page in range(1, SEARCH_PAGES + 1):
                try:
                    data = tmdb.get(
                        SEARCH_ENDPOINT,
                        {
                            "query": query,
                            "page": page,
                            "include_adult": False,
                        },
                    )
                except (TMDBNotFoundError, TMDBRequestError):
                    continue

                for movie in data.get("results", []):
                    movie_id = movie.get("id")
                    if movie_id is None:
                        continue

                    candidates.append(
                        Candidate(
                            movie_id=movie_id,
                            source=self.name,
                            metadata=movie,
                        )
                    )

                total_pages = data.get("total_pages") or SEARCH_PAGES
                if page >= total_pages:
                    break

        return candidates


class DiscoverySource(CatalogueSource):
    name = "discovery"

    def __init__(self, pages, min_vote_count, min_rating, original_language):
        self.pages = pages
        self.min_vote_count = min_vote_count
        self.min_rating = min_rating
        self.original_language = original_language

    def discover(self, tmdb, detail_cache):
        candidates = []

        for start_year, end_year in DECADES:
            for genre_name, genre_id in GENRES:
                params = {
                    "sort_by": "vote_average.desc",
                    "primary_release_date.gte": f"{start_year}-01-01",
                    "primary_release_date.lte": f"{end_year}-12-31",
                    "with_genres": genre_id,
                    "vote_count.gte": self.min_vote_count,
                    "vote_average.gte": self.min_rating,
                    "include_adult": False,
                    "include_video": False,
                }

                if self.original_language:
                    params["with_original_language"] = self.original_language

                for page in range(1, self.pages + 1):
                    page_params = params.copy()
                    page_params["page"] = page

                    try:
                        data = tmdb.get(DISCOVER_ENDPOINT, page_params)
                    except (TMDBNotFoundError, TMDBRequestError):
                        continue

                    for movie in data.get("results", []):
                        movie_id = movie.get("id")
                        if movie_id is None:
                            continue

                        candidates.append(
                            Candidate(
                                movie_id=movie_id,
                                source=self.name,
                                metadata=movie,
                                genre_name=genre_name,
                            )
                        )

                    total_pages = data.get("total_pages") or self.pages
                    if page >= total_pages:
                        break

        return candidates


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build and maintain the CineMatch movie catalogue."
    )
    parser.add_argument("--collection-id", type=int, action="append", default=[])
    parser.add_argument("--movie-id", type=int, action="append", default=[])
    parser.add_argument("--search-query", action="append", default=[])
    parser.add_argument("--discovery", action="store_true")
    parser.add_argument("--pages-per-discovery", type=int, default=2)
    parser.add_argument("--max-new-movies", type=int, default=1000)
    parser.add_argument("--min-vote-count", type=int, default=300)
    parser.add_argument("--min-rating", type=float, default=5.0)
    parser.add_argument("--original-language")
    parser.add_argument("--include-extra-content", action="store_true")

    args = parser.parse_args()

    if args.pages_per_discovery < 1:
        parser.error("--pages-per-discovery must be at least 1")

    if args.max_new_movies < 0:
        parser.error("--max-new-movies must be 0 or greater")

    if args.min_vote_count < 0:
        parser.error("--min-vote-count must be 0 or greater")

    if not (
        args.collection_id or
        args.movie_id or
        args.search_query or
        args.discovery
    ):
        parser.error(
            "choose at least one source: --collection-id, --movie-id, "
            "--search-query, or --discovery"
        )

    return args


def fetch_movie_summary(tmdb, movie_id, detail_cache):
    if movie_id not in detail_cache:
        detail_cache[movie_id] = tmdb.get(f"/movie/{movie_id}")

    return detail_cache[movie_id]


def fetch_collection_candidates(tmdb, collection_id):
    try:
        collection_data = tmdb.get(f"/collection/{collection_id}")
    except (TMDBNotFoundError, TMDBRequestError):
        return []

    collection_name = collection_data.get("name") or ""
    candidates = []

    for movie in collection_data.get("parts", []):
        movie_id = movie.get("id")
        if movie_id is None:
            continue

        candidates.append(
            Candidate(
                movie_id=movie_id,
                source=OfficialCollectionSource.name,
                metadata=movie,
                collection_id=collection_id,
                collection_name=collection_name,
            )
        )

    return candidates


def build_sources(args):
    sources = []

    if args.collection_id or args.movie_id:
        sources.append(
            OfficialCollectionSource(args.collection_id, args.movie_id)
        )

    if args.search_query:
        sources.append(FranchiseSearchSource(args.search_query))

    if args.discovery:
        sources.append(
            DiscoverySource(
                args.pages_per_discovery,
                args.min_vote_count,
                args.min_rating,
                args.original_language,
            )
        )

    return sources


def merge_candidates(candidates):
    merged = {}

    for candidate in candidates:
        if candidate.movie_id not in merged:
            merged[candidate.movie_id] = candidate
            continue

        existing = merged[candidate.movie_id]

        if not existing.collection_id and candidate.collection_id:
            existing.collection_id = candidate.collection_id
            existing.collection_name = candidate.collection_name

        if not existing.genre_name and candidate.genre_name:
            existing.genre_name = candidate.genre_name

    return list(merged.values())


def discover_candidates(tmdb, sources, detail_cache):
    candidates = []

    for source in sources:
        candidates.extend(source.discover(tmdb, detail_cache))

    return merge_candidates(candidates)


def get_collection_name(details, candidate):
    collection = details.get("belongs_to_collection") or {}
    return (
        collection.get("name") or
        candidate.collection_name or
        ""
    )


def get_collection_id(details, candidate):
    collection = details.get("belongs_to_collection") or {}
    return collection.get("id") or candidate.collection_id


def get_genre_names(details):
    return [
        str(genre.get("name", "")).lower()
        for genre in details.get("genres", [])
    ]


def has_excluded_content_marker(details):
    genre_names = get_genre_names(details)

    if "documentary" in genre_names:
        return True

    collection = details.get("belongs_to_collection") or {}
    searchable_text = " ".join([
        str(details.get("title") or ""),
        str(details.get("original_title") or ""),
        str(details.get("overview") or ""),
        str(details.get("tagline") or ""),
        str(collection.get("name") or ""),
    ]).lower()

    return any(
        marker in searchable_text
        for marker in EXCLUDED_CONTENT_MARKERS
    )


def quality_rejection_reason(details, args):
    if details.get("adult"):
        return "adult"

    if details.get("video"):
        return "not movie release"

    if args.original_language:
        original_language = details.get("original_language")
        if original_language != args.original_language:
            return "original language"

    if not (details.get("overview") or "").strip():
        return "missing overview"

    if not (details.get("release_date") or "").strip():
        return "missing release date"

    if (details.get("runtime") or 0) < 60:
        return "runtime below 60 minutes"

    if (details.get("vote_count") or 0) < args.min_vote_count:
        return "vote count"

    if (details.get("vote_average") or 0) < args.min_rating:
        return "rating"

    if not args.include_extra_content and has_excluded_content_marker(details):
        return "extra content"

    return None


def apply_catalogue_metadata(movie, details, candidate, schema_columns):
    collection_name = get_collection_name(details, candidate)

    movie["collection"] = collection_name

    if "collection" not in schema_columns:
        return movie

    movie["collection"] = collection_name
    return movie


def new_report(movies_before):
    return {
        "movies_before": movies_before,
        "movies_added": 0,
        "already_existing": 0,
        "rejected": 0,
        "missing_failed": 0,
        "save_skipped": 0,
        "excluded_by_limit": 0,
        "collections_added": set(),
        "genres_added": set(),
    }


def save_batch(dataset, current_df, pending_entries, existing_ids, report):
    if not pending_entries:
        return current_df

    movies = [
        entry["movie"]
        for entry in pending_entries
    ]
    updated_df = dataset.update(current_df, movies)

    added = dataset.last_update_stats["added"]
    skipped = dataset.last_update_stats["skipped"]

    report["movies_added"] += added
    report["save_skipped"] += skipped

    if added > 0:
        for entry in pending_entries:
            movie_id = entry["candidate"].movie_id
            existing_ids.add(movie_id)

            collection_id = get_collection_id(
                entry["details"],
                entry["candidate"],
            )
            collection_name = get_collection_name(
                entry["details"],
                entry["candidate"],
            )

            if collection_id or collection_name:
                report["collections_added"].add(
                    collection_id or collection_name
                )

            for genre in entry["details"].get("genres", []):
                genre_name = genre.get("name")
                if genre_name:
                    report["genres_added"].add(genre_name)

            if entry["candidate"].genre_name:
                report["genres_added"].add(entry["candidate"].genre_name)

    pending_entries.clear()
    return updated_df


def process_candidates(
    tmdb,
    dataset,
    current_df,
    candidates,
    detail_cache,
    existing_ids,
    args,
    report,
    pending_entries,
):
    schema_columns = set(current_df.columns)
    total_candidates = len(candidates)

    for index, candidate in enumerate(candidates, start=1):
        if candidate.movie_id in existing_ids:
            report["already_existing"] += 1
            continue

        try:
            details = fetch_movie_summary(
                tmdb,
                candidate.movie_id,
                detail_cache,
            )
        except (TMDBNotFoundError, TMDBRequestError):
            report["missing_failed"] += 1
            continue

        rejection_reason = quality_rejection_reason(details, args)
        if rejection_reason:
            report["rejected"] += 1
            continue

        title = (
            details.get("title") or
            candidate.metadata.get("title") or
            candidate.movie_id
        )
        print(f"Processing {index}/{total_candidates}: {title}")

        try:
            movie = tmdb.fetch_movie_details(candidate.movie_id)
        except (TMDBNotFoundError, TMDBRequestError):
            report["missing_failed"] += 1
            continue

        pending_entries.append({
            "movie": apply_catalogue_metadata(
                movie,
                details,
                candidate,
                schema_columns,
            ),
            "details": details,
            "candidate": candidate,
        })

        if len(pending_entries) >= BATCH_SIZE:
            current_df = save_batch(
                dataset,
                current_df,
                pending_entries,
                existing_ids,
                report,
            )

    return save_batch(
        dataset,
        current_df,
        pending_entries,
        existing_ids,
        report,
    )


def print_report(report, final_catalogue_size):
    movies_skipped = (
        report["already_existing"] +
        report["rejected"] +
        report["missing_failed"] +
        report["save_skipped"] +
        report["excluded_by_limit"]
    )

    print("Movies before:", report["movies_before"])
    print("Movies added:", report["movies_added"])
    print("Movies skipped:", movies_skipped)
    print("Collections added:", len(report["collections_added"]))
    print("Genres added:", len(report["genres_added"]))
    print("Final catalogue size:", final_catalogue_size)


def main():
    args = parse_args()
    tmdb = TMDBService()
    dataset = DatasetService()
    similarity = SimilarityService()
    detail_cache = {}
    pending_entries = []
    interrupted = False

    existing_df = dataset.load_dataframe()
    current_df = existing_df
    existing_ids = dataset.get_existing_ids(existing_df)
    report = new_report(len(existing_ids))

    try:
        sources = build_sources(args)
        candidates = discover_candidates(tmdb, sources, detail_cache)

        new_candidates = [
            candidate
            for candidate in candidates
            if candidate.movie_id not in existing_ids
        ]
        report["already_existing"] += len(candidates) - len(new_candidates)

        limited_candidates = new_candidates[:args.max_new_movies]
        report["excluded_by_limit"] += (
            len(new_candidates) - len(limited_candidates)
        )

        current_df = process_candidates(
            tmdb,
            dataset,
            current_df,
            limited_candidates,
            detail_cache,
            existing_ids,
            args,
            report,
            pending_entries,
        )
    except KeyboardInterrupt:
        interrupted = True
        current_df = save_batch(
            dataset,
            current_df,
            pending_entries,
            existing_ids,
            report,
        )

    if report["movies_added"] > 0:
        similarity.rebuild(verbose=False)

    if interrupted:
        print("Interrupted safely; progress saved")

    print_report(report, len(dataset.get_existing_ids(current_df)))


if __name__ == "__main__":
    main()
