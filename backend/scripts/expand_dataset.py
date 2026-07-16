import argparse
import os
import sys
import time
from datetime import date

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from services.dataset_service import DatasetService
from services.similarity_service import SimilarityService
from services.tmdb_service import TMDBNotFoundError, TMDBRequestError, TMDBService


DISCOVER_ENDPOINT = "/discover/movie"
SEARCH_ENDPOINT = "/search/movie"
SEARCH_PAGES = 5
BATCH_SIZE = 10

YEAR_RANGES = [
    (1960, 1969),
    (1970, 1979),
    (1980, 1989),
    (1990, 1999),
    (2000, 2009),
    (2010, 2019),
    (2020, date.today().year),
]

RANGE_SORTS = [
    ("popularity.desc", {}),
    ("vote_count.desc", {}),
    ("vote_average.desc", {"vote_count.gte": 500}),
]

GENRES = [
    ("Action", 28),
    ("Adventure", 12),
    ("Animation", 16),
    ("Comedy", 35),
    ("Crime", 80),
    ("Documentary", 99),
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Expand the movie dataset using TMDB discovery and search."
    )
    parser.add_argument("--pages-per-range", type=int, default=5)
    parser.add_argument("--pages-per-genre", type=int, default=3)
    parser.add_argument("--max-new-movies", type=int, default=1000)
    parser.add_argument("--search-query", action="append", default=[])
    parser.add_argument("--targeted-only", action="store_true")
    parser.add_argument("--min-vote-count", type=int, default=300)
    parser.add_argument("--min-rating", type=float, default=5.0)
    parser.add_argument("--original-language")
    parser.add_argument("--collection-search", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--include-extra-content", action="store_true")

    args = parser.parse_args()

    if args.pages_per_range < 1:
        parser.error("--pages-per-range must be at least 1")

    if args.pages_per_genre < 1:
        parser.error("--pages-per-genre must be at least 1")

    if args.max_new_movies < 0:
        parser.error("--max-new-movies must be 0 or greater")

    if args.min_vote_count < 0:
        parser.error("--min-vote-count must be 0 or greater")

    return args


def add_discovered_movies(movie_ids, seen_ids, movie_metadata, results):
    for movie in results:
        movie_id = movie.get("id")

        if movie_id is None or movie_id in seen_ids:
            continue

        seen_ids.add(movie_id)
        movie_ids.append(movie_id)
        movie_metadata[movie_id] = movie


def fetch_discover_movies(
    tmdb,
    params,
    pages,
    movie_ids,
    seen_ids,
    movie_metadata,
):
    for page in range(1, pages + 1):
        page_params = params.copy()
        page_params["page"] = page
        page_params["include_adult"] = False
        page_params["include_video"] = False

        try:
            data = tmdb.get(DISCOVER_ENDPOINT, page_params)
        except TMDBNotFoundError:
            continue
        except TMDBRequestError:
            continue

        add_discovered_movies(
            movie_ids,
            seen_ids,
            movie_metadata,
            data.get("results", []),
        )

        total_pages = data.get("total_pages") or pages
        if page >= total_pages:
            break


def fetch_search_movie_ids(tmdb, search_queries):
    movie_ids = []
    seen_ids = set()
    movie_metadata = {}

    for query in search_queries:
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
            except TMDBNotFoundError:
                continue
            except TMDBRequestError:
                continue

            add_discovered_movies(
                movie_ids,
                seen_ids,
                movie_metadata,
                data.get("results", []),
            )

            total_pages = data.get("total_pages") or SEARCH_PAGES
            if page >= total_pages:
                break

    return movie_ids, movie_metadata


def fetch_broad_movie_ids(
    tmdb,
    pages_per_range,
    pages_per_genre,
    original_language=None,
):
    movie_ids = []
    seen_ids = set()
    movie_metadata = {}

    for start_year, end_year in YEAR_RANGES:
        for sort_by, extra_params in RANGE_SORTS:
            params = {
                "sort_by": sort_by,
                "primary_release_date.gte": f"{start_year}-01-01",
                "primary_release_date.lte": f"{end_year}-12-31",
            }
            params.update(extra_params)

            if original_language:
                params["with_original_language"] = original_language

            fetch_discover_movies(
                tmdb,
                params,
                pages_per_range,
                movie_ids,
                seen_ids,
                movie_metadata,
            )

    for _genre_name, genre_id in GENRES:
        params = {
            "sort_by": "popularity.desc",
            "with_genres": genre_id,
            "vote_count.gte": 200,
        }

        if original_language:
            params["with_original_language"] = original_language

        fetch_discover_movies(
            tmdb,
            params,
            pages_per_genre,
            movie_ids,
            seen_ids,
            movie_metadata,
        )

    return movie_ids, movie_metadata


def fetch_movie_summary(tmdb, movie_id, detail_cache):
    if movie_id not in detail_cache:
        detail_cache[movie_id] = tmdb.get(f"/movie/{movie_id}")

    return detail_cache[movie_id]


def expand_targeted_collections(tmdb, movie_ids, movie_metadata, detail_cache):
    seen_ids = set(movie_ids)
    seen_collections = set()

    for movie_id in list(movie_ids):
        try:
            details = fetch_movie_summary(tmdb, movie_id, detail_cache)
        except TMDBNotFoundError:
            continue
        except TMDBRequestError:
            continue

        collection = details.get("belongs_to_collection") or {}
        collection_id = collection.get("id")

        if not collection_id or collection_id in seen_collections:
            continue

        seen_collections.add(collection_id)

        try:
            collection_data = tmdb.get(f"/collection/{collection_id}")
        except TMDBNotFoundError:
            continue
        except TMDBRequestError:
            continue

        add_discovered_movies(
            movie_ids,
            seen_ids,
            movie_metadata,
            collection_data.get("parts", []),
        )


def merge_movie_metadata(target_metadata, source_metadata):
    for movie_id, metadata in source_metadata.items():
        if movie_id not in target_metadata:
            target_metadata[movie_id] = metadata


def combine_candidate_ids(targeted_ids, broad_ids):
    candidate_ids = []
    seen_ids = set()

    for movie_id in targeted_ids + broad_ids:
        if movie_id in seen_ids:
            continue

        seen_ids.add(movie_id)
        candidate_ids.append(movie_id)

    return candidate_ids


def get_collection_name(details):
    collection = details.get("belongs_to_collection") or {}
    return collection.get("name") or ""


def get_release_year(details):
    release_date = details.get("release_date") or ""
    return release_date[:4] if len(release_date) >= 4 else ""


def get_genre_names(details):
    return [
        str(genre.get("name", "")).lower()
        for genre in details.get("genres", [])
    ]


def has_excluded_content_marker(details):
    genre_names = get_genre_names(details)

    if "documentary" in genre_names:
        return True

    searchable_text = " ".join([
        str(details.get("title") or ""),
        str(details.get("original_title") or ""),
        str(details.get("overview") or ""),
        str(details.get("tagline") or ""),
        get_collection_name(details),
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


def print_preview(details, status):
    title = details.get("title") or details.get("original_title") or "Untitled"
    year = get_release_year(details) or "unknown"
    rating = details.get("vote_average") or 0
    vote_count = details.get("vote_count") or 0
    runtime = details.get("runtime") or 0
    collection = get_collection_name(details) or "None"

    print(
        f"Preview: {title} ({year}) "
        f"rating={rating} "
        f"vote_count={vote_count} "
        f"runtime={runtime} "
        f"collection={collection} "
        f"status={status}"
    )


def apply_schema_extras(movie, details, schema_columns):
    if "collection" in schema_columns:
        movie["collection"] = get_collection_name(details)

    return movie


def save_batch(dataset, current_df, pending_movies):
    if not pending_movies:
        return current_df, 0, 0

    updated_df = dataset.update(current_df, pending_movies)
    added = dataset.last_update_stats["added"]
    skipped = dataset.last_update_stats["skipped"]
    pending_movies.clear()

    return updated_df, added, skipped


def process_candidates(
    tmdb,
    dataset,
    current_df,
    movie_ids,
    movie_metadata,
    detail_cache,
    args,
    counters,
    pending_movies,
):
    total_movies = len(movie_ids)
    schema_columns = set(current_df.columns)

    for index, movie_id in enumerate(movie_ids, start=1):
        fallback_title = movie_metadata.get(movie_id, {}).get("title") or movie_id

        try:
            details = fetch_movie_summary(tmdb, movie_id, detail_cache)
        except TMDBNotFoundError:
            counters["missing_failed"] += 1
            continue
        except TMDBRequestError:
            counters["missing_failed"] += 1
            continue

        rejection_reason = quality_rejection_reason(details, args)

        if rejection_reason:
            counters["rejected_by_quality_filter"] += 1
            if args.preview:
                print_preview(details, f"rejected: {rejection_reason}")
            continue

        if args.preview:
            print_preview(details, "accepted")
            continue

        title = details.get("title") or fallback_title
        print(f"Processing {index}/{total_movies}: {title}")

        try:
            movie = tmdb.fetch_movie_details(movie_id)
        except TMDBNotFoundError:
            counters["missing_failed"] += 1
            continue
        except TMDBRequestError:
            counters["missing_failed"] += 1
            continue

        pending_movies.append(
            apply_schema_extras(movie, details, schema_columns)
        )

        if len(pending_movies) >= BATCH_SIZE:
            current_df, added, skipped = save_batch(
                dataset,
                current_df,
                pending_movies,
            )
            counters["successfully_saved"] += added
            counters["already_existing"] += skipped

    current_df, added, skipped = save_batch(
        dataset,
        current_df,
        pending_movies,
    )
    counters["successfully_saved"] += added
    counters["already_existing"] += skipped

    return current_df


def print_summary(counters, final_movie_count, total_runtime):
    print("discovered:", counters["discovered"])
    print("already existing:", counters["already_existing"])
    print("rejected by quality filter:", counters["rejected_by_quality_filter"])
    print("missing/failed:", counters["missing_failed"])
    print("successfully saved:", counters["successfully_saved"])
    print("excluded by limit:", counters["excluded_by_limit"])
    print("final movie count:", final_movie_count)
    print("total runtime:", f"{total_runtime:.2f} seconds")


def main():
    args = parse_args()
    start_time = time.perf_counter()

    tmdb = TMDBService()
    dataset = DatasetService()
    similarity = SimilarityService()
    detail_cache = {}
    pending_movies = []
    counters = {
        "discovered": 0,
        "already_existing": 0,
        "rejected_by_quality_filter": 0,
        "missing_failed": 0,
        "successfully_saved": 0,
        "excluded_by_limit": 0,
    }

    existing_df = dataset.load_dataframe()
    updated_df = existing_df
    existing_ids = dataset.get_existing_ids(existing_df)
    interrupted = False

    try:
        targeted_ids, targeted_metadata = fetch_search_movie_ids(
            tmdb,
            args.search_query,
        )

        if args.collection_search:
            expand_targeted_collections(
                tmdb,
                targeted_ids,
                targeted_metadata,
                detail_cache,
            )

        if args.targeted_only:
            broad_ids = []
            broad_metadata = {}
        else:
            broad_ids, broad_metadata = fetch_broad_movie_ids(
                tmdb,
                args.pages_per_range,
                args.pages_per_genre,
                args.original_language,
            )

        movie_metadata = {}
        merge_movie_metadata(movie_metadata, targeted_metadata)
        merge_movie_metadata(movie_metadata, broad_metadata)

        movie_ids = combine_candidate_ids(targeted_ids, broad_ids)
        counters["discovered"] = len(movie_ids)

        new_candidate_ids = [
            movie_id
            for movie_id in movie_ids
            if movie_id not in existing_ids
        ]
        counters["already_existing"] = len(movie_ids) - len(new_candidate_ids)

        limited_candidate_ids = new_candidate_ids[:args.max_new_movies]
        counters["excluded_by_limit"] = (
            len(new_candidate_ids) - len(limited_candidate_ids)
        )

        updated_df = process_candidates(
            tmdb,
            dataset,
            updated_df,
            limited_candidate_ids,
            movie_metadata,
            detail_cache,
            args,
            counters,
            pending_movies,
        )
    except KeyboardInterrupt:
        interrupted = True

        if not args.preview:
            updated_df, added, skipped = save_batch(
                dataset,
                updated_df,
                pending_movies,
            )
            counters["successfully_saved"] += added
            counters["already_existing"] += skipped

    if not args.preview and counters["successfully_saved"] > 0:
        similarity.rebuild(verbose=False)

    total_runtime = time.perf_counter() - start_time

    if interrupted:
        print("Interrupted safely; progress saved")

    print_summary(
        counters,
        len(dataset.get_existing_ids(updated_df)),
        total_runtime,
    )


if __name__ == "__main__":
    main()
