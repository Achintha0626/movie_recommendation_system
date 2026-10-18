"""TMDB API client for TV series data.

Reuses the shared TMDBService transport (session, rate-limit handling, error
classes) but targets TV-specific endpoints (/tv, /discover/tv).

Key TMDB difference from the movie API:
    TV keywords are nested under ``keywords.results`` instead of
    ``keywords.keywords``.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from datetime import date, timedelta

from services.tmdb_service import TMDBNotFoundError, TMDBRequestError, TMDBService

logger = logging.getLogger(__name__)

# TMDB TV genre IDs — mirrors the movie GENRES list in catalogue_builder.py
TV_GENRES = [
    ("Action & Adventure", 10759),
    ("Animation", 16),
    ("Comedy", 35),
    ("Crime", 80),
    ("Documentary", 99),
    ("Drama", 18),
    ("Family", 10751),
    ("Kids", 10762),
    ("Mystery", 9648),
    ("Reality", 10764),
    ("Sci-Fi & Fantasy", 10765),
    ("Soap", 10766),
    ("Talk", 10767),
    ("War & Politics", 10768),
    ("Western", 37),
]

DISCOVER_TV_ENDPOINT = "/discover/tv"

EXPANDED_ERA_RANGES = [
    (1950, 1969),
    (1970, 1979),
    (1980, 1989),
    (1990, 1999),
    (2000, 2009),
    (2010, 2015),
    (2016, 2020),
    (2021, 2026),
]

# Legacy alias for backward compatibility with existing tests/callers
DECADE_RANGES = [
    (1990, 1999),
    (2000, 2009),
    (2010, 2019),
    (2020, 2026),
]

_RATE_LIMIT_DELAY = 0.05


class TVTMDBService:
    """Encapsulates TMDB API calls specific to TV series."""

    def __init__(self, tmdb: TMDBService | None = None):
        self.tmdb = tmdb or TMDBService()

    # ------------------------------------------------------------------
    # Safe transport with retry / backoff
    # ------------------------------------------------------------------

    def safe_get(
        self,
        endpoint: str,
        params: dict | None = None,
        max_retries: int = 3,
    ) -> dict:
        """Call TMDB with automatic exponential backoff for rate limits and transient errors."""
        for attempt in range(max_retries):
            try:
                return self.tmdb.get(endpoint, params)
            except TMDBNotFoundError:
                raise
            except TMDBRequestError as exc:
                if exc.status_code == 429:
                    wait_time = 1.0 * (2**attempt)
                    logger.warning(
                        "Rate limited (429) on %s. Backing off for %.1fs (attempt %d/%d)",
                        endpoint,
                        wait_time,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(wait_time)
                    continue
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.3 * (attempt + 1))
            except Exception as exc:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.3 * (attempt + 1))

        raise TMDBRequestError(500, endpoint)

    # ------------------------------------------------------------------
    # Single-series detail fetch
    # ------------------------------------------------------------------

    def fetch_series_details(self, series_id: int) -> dict:
        """Fetch full TV series metadata in a single TMDB request.

        Uses ``append_to_response`` to include keywords and aggregate
        credits in one API call, mirroring the movie pipeline's
        ``fetch_movie_details`` pattern.
        """
        details = self.safe_get(
            f"/tv/{series_id}",
            {"append_to_response": "keywords,aggregate_credits"},
        )

        # --- keywords (TV uses 'results', not 'keywords') ---
        keywords_data = details.get("keywords") or {}
        keyword_list = keywords_data.get("results") or []
        keyword_text = " ".join(
            kw.get("name", "").strip()
            for kw in keyword_list
            if kw and kw.get("name")
        )

        # --- genres ---
        genre_list = details.get("genres") or []
        genres = " ".join(
            genre.get("name", "").strip()
            for genre in genre_list
            if genre and genre.get("name")
        )

        # --- aggregate credits (top 5 cast) ---
        credits = details.get("aggregate_credits") or {}
        cast_list = (credits.get("cast") or [])[:5]
        cast = " ".join(
            person.get("name", "").strip()
            for person in cast_list
            if person and person.get("name")
        )

        # --- created-by (analogous to director for movies) ---
        created_by_list = details.get("created_by") or []
        created_by = " ".join(
            person.get("name", "").strip()
            for person in created_by_list
            if person and person.get("name")
        )

        # --- production companies ---
        company_list = details.get("production_companies") or []
        production_companies = " ".join(
            company.get("name", "").strip()
            for company in company_list
            if company and company.get("name")
        )

        # --- networks ---
        network_list = details.get("networks") or []
        networks = " ".join(
            network.get("name", "").strip()
            for network in network_list
            if network and network.get("name")
        )

        # --- spoken languages ---
        lang_list = details.get("spoken_languages") or []
        spoken_languages = " ".join(
            lang.get("english_name", "").strip()
            for lang in lang_list
            if lang and lang.get("english_name")
        )

        raw_id = details.get("id")
        coerced_id = int(raw_id) if raw_id is not None else None

        return {
            "id": coerced_id,
            "name": str(details.get("name") or details.get("original_name") or "Untitled").strip(),
            "original_name": str(details.get("original_name") or "").strip(),
            "overview": str(details.get("overview") or "").strip(),
            "first_air_date": str(details.get("first_air_date") or "").strip(),
            "genres": genres,
            "original_language": str(details.get("original_language") or "").strip(),
            "popularity": float(details.get("popularity") or 0.0),
            "vote_average": float(details.get("vote_average") or 0.0),
            "vote_count": int(details.get("vote_count") or 0),
            "poster_path": str(details.get("poster_path") or "").strip(),
            "backdrop_path": str(details.get("backdrop_path") or "").strip(),
            "number_of_seasons": int(details.get("number_of_seasons") or 0),
            "number_of_episodes": int(details.get("number_of_episodes") or 0),
            "status": str(details.get("status") or "").strip(),
            "keywords": keyword_text,
            "cast": cast,
            "created_by": created_by,
            "production_companies": production_companies,
            "networks": networks,
            "spoken_languages": spoken_languages,
            "tagline": str(details.get("tagline") or "").strip(),
        }

    # ------------------------------------------------------------------
    # Concurrent batch detail fetching
    # ------------------------------------------------------------------

    def fetch_series_details_batch(
        self,
        series_ids: list[int],
        max_workers: int = 8,
        delay: float = _RATE_LIMIT_DELAY,
        on_progress=None,
    ) -> list[dict]:
        """Fetch details for a batch of series IDs concurrently with bounded thread pool.

        Handles missing series, rate limits, and network errors safely.
        """
        results: list[dict] = []
        total = len(series_ids)
        if total == 0:
            return results

        logger.info("Fetching details for %d series with %d workers...", total, max_workers)

        completed_count = 0
        skipped_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {
                executor.submit(self.fetch_series_details, sid): sid
                for sid in series_ids
            }

            for future in as_completed(future_to_id):
                sid = future_to_id[future]
                completed_count += 1
                try:
                    detail = future.result()
                    if detail and detail.get("id") is not None:
                        results.append(detail)
                except TMDBNotFoundError:
                    skipped_count += 1
                    logger.debug("Series %d not found on TMDB", sid)
                except Exception as exc:
                    skipped_count += 1
                    logger.warning("Failed to fetch details for series %d: %s", sid, exc)

                if on_progress and (completed_count % 100 == 0 or completed_count == total):
                    on_progress(completed_count, total, len(results), skipped_count)

                if delay > 0:
                    time.sleep(delay)

        return results

    # ------------------------------------------------------------------
    # Discovery Strategies
    # ------------------------------------------------------------------

    def fetch_source_series(self, pages_per_source: int = 5) -> list[int]:
        """Gather series IDs from popular, top-rated, on-the-air, and airing-today lists.

        Fetches up to ``pages_per_source`` pages per endpoint.
        """
        series_ids: set[int] = set()

        sources = [
            "/tv/popular",
            "/tv/top_rated",
            "/tv/on_the_air",
            "/tv/airing_today",
        ]

        for source in sources:
            for page in range(1, pages_per_source + 1):
                try:
                    data = self.safe_get(source, {"page": page})
                except (TMDBNotFoundError, TMDBRequestError):
                    continue

                for series in data.get("results", []):
                    series_id = series.get("id")
                    if series_id is not None:
                        series_ids.add(int(series_id))

                total_pages = data.get("total_pages", 1) or 1
                if page >= total_pages:
                    break

                time.sleep(_RATE_LIMIT_DELAY)

        return list(series_ids)

    def discover_series(
        self,
        pages_per_slot: int = 2,
        min_vote_count: int = 100,
        min_rating: float = 5.0,
        original_language: str | None = None,
        eras: list[tuple[int, int]] | None = None,
    ) -> list[int]:
        """Discover TV series across decades/eras × genres.

        Maintains backward compatibility with original discover_series method.
        """
        series_ids: set[int] = set()
        active_eras = eras or DECADE_RANGES

        for start_year, end_year in active_eras:
            for genre_name, genre_id in TV_GENRES:
                params: dict = {
                    "sort_by": "vote_average.desc",
                    "first_air_date.gte": f"{start_year}-01-01",
                    "first_air_date.lte": f"{end_year}-12-31",
                    "with_genres": genre_id,
                    "vote_count.gte": min_vote_count,
                    "vote_average.gte": min_rating,
                    "include_adult": False,
                }

                if original_language:
                    params["with_original_language"] = original_language

                for page in range(1, pages_per_slot + 1):
                    page_params = params.copy()
                    page_params["page"] = page

                    try:
                        data = self.safe_get(DISCOVER_TV_ENDPOINT, page_params)
                    except (TMDBNotFoundError, TMDBRequestError):
                        continue

                    for series in data.get("results", []):
                        series_id = series.get("id")
                        if series_id is not None:
                            series_ids.add(int(series_id))

                    total_pages = data.get("total_pages") or pages_per_slot
                    if page >= total_pages:
                        break

                    time.sleep(_RATE_LIMIT_DELAY)

        return list(series_ids)

    def discover_by_popularity(
        self,
        pages_per_era: int = 10,
        min_vote_count: int = 15,
        eras: list[tuple[int, int]] | None = None,
        target_count: int | None = None,
    ) -> set[int]:
        """Discover series sorted by popularity across distinct release eras."""
        discovered: set[int] = set()
        active_eras = eras or EXPANDED_ERA_RANGES

        for start_year, end_year in active_eras:
            if target_count and len(discovered) >= target_count:
                break

            params = {
                "sort_by": "popularity.desc",
                "first_air_date.gte": f"{start_year}-01-01",
                "first_air_date.lte": f"{end_year}-12-31",
                "vote_count.gte": min_vote_count,
                "include_adult": False,
            }

            for page in range(1, pages_per_era + 1):
                if target_count and len(discovered) >= target_count:
                    break

                page_params = params.copy()
                page_params["page"] = page

                try:
                    data = self.safe_get(DISCOVER_TV_ENDPOINT, page_params)
                except (TMDBNotFoundError, TMDBRequestError):
                    continue

                results = data.get("results") or []
                for item in results:
                    sid = item.get("id")
                    if sid is not None:
                        discovered.add(int(sid))

                total_pages = data.get("total_pages", 1) or 1
                if page >= total_pages:
                    break

                time.sleep(_RATE_LIMIT_DELAY)

        return discovered

    def discover_by_rating(
        self,
        pages_per_era: int = 6,
        min_vote_count: int = 40,
        min_rating: float = 6.5,
        eras: list[tuple[int, int]] | None = None,
        target_count: int | None = None,
    ) -> set[int]:
        """Discover top-rated series with reliable vote counts across eras."""
        discovered: set[int] = set()
        active_eras = eras or EXPANDED_ERA_RANGES

        for start_year, end_year in active_eras:
            if target_count and len(discovered) >= target_count:
                break

            params = {
                "sort_by": "vote_average.desc",
                "first_air_date.gte": f"{start_year}-01-01",
                "first_air_date.lte": f"{end_year}-12-31",
                "vote_count.gte": min_vote_count,
                "vote_average.gte": min_rating,
                "include_adult": False,
            }

            for page in range(1, pages_per_era + 1):
                if target_count and len(discovered) >= target_count:
                    break

                page_params = params.copy()
                page_params["page"] = page

                try:
                    data = self.safe_get(DISCOVER_TV_ENDPOINT, page_params)
                except (TMDBNotFoundError, TMDBRequestError):
                    continue

                for item in data.get("results") or []:
                    sid = item.get("id")
                    if sid is not None:
                        discovered.add(int(sid))

                total_pages = data.get("total_pages", 1) or 1
                if page >= total_pages:
                    break

                time.sleep(_RATE_LIMIT_DELAY)

        return discovered

    def discover_by_genres(
        self,
        pages_per_genre: int = 8,
        min_vote_count: int = 20,
        sort_by: str = "popularity.desc",
        target_count: int | None = None,
    ) -> set[int]:
        """Discover series systematically across all recognized TMDB TV genres."""
        discovered: set[int] = set()

        for genre_name, genre_id in TV_GENRES:
            if target_count and len(discovered) >= target_count:
                break

            params = {
                "sort_by": sort_by,
                "with_genres": genre_id,
                "vote_count.gte": min_vote_count,
                "include_adult": False,
            }

            for page in range(1, pages_per_genre + 1):
                if target_count and len(discovered) >= target_count:
                    break

                page_params = params.copy()
                page_params["page"] = page

                try:
                    data = self.safe_get(DISCOVER_TV_ENDPOINT, page_params)
                except (TMDBNotFoundError, TMDBRequestError):
                    continue

                for item in data.get("results") or []:
                    sid = item.get("id")
                    if sid is not None:
                        discovered.add(int(sid))

                total_pages = data.get("total_pages", 1) or 1
                if page >= total_pages:
                    break

                time.sleep(_RATE_LIMIT_DELAY)

        return discovered

    def discover_recent_air_dates(
        self,
        days_back: int = 730,
        pages: int = 15,
        min_vote_count: int = 10,
    ) -> set[int]:
        """Discover series that recently aired or are currently on air."""
        discovered: set[int] = set()
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()

        params = {
            "sort_by": "popularity.desc",
            "air_date.gte": cutoff,
            "vote_count.gte": min_vote_count,
            "include_adult": False,
        }

        for page in range(1, pages + 1):
            page_params = params.copy()
            page_params["page"] = page

            try:
                data = self.safe_get(DISCOVER_TV_ENDPOINT, page_params)
            except (TMDBNotFoundError, TMDBRequestError):
                continue

            for item in data.get("results") or []:
                sid = item.get("id")
                if sid is not None:
                    discovered.add(int(sid))

            total_pages = data.get("total_pages", 1) or 1
            if page >= total_pages:
                break

            time.sleep(_RATE_LIMIT_DELAY)

        return discovered

    def discover_multi_strategy(
        self,
        target_count: int = 4000,
        include_sources: bool = True,
        pages_per_era: int = 10,
        pages_per_genre: int = 8,
    ) -> list[int]:
        """Orchestrate multiple discovery strategies to gather diverse, high-quality TV series.

        Deduplicates strictly by integer TMDB series ID.
        """
        all_candidate_ids: set[int] = set()

        # Strategy 1: Standard curated lists
        if include_sources:
            logger.info("Discover Strategy 1: Curated sources (popular, top-rated, on-the-air, airing-today)...")
            source_ids = self.fetch_source_series(pages_per_source=5)
            all_candidate_ids.update(source_ids)
            logger.info("Candidates after Strategy 1: %d", len(all_candidate_ids))

        # Strategy 2: Era-based popularity discovery
        if len(all_candidate_ids) < target_count:
            logger.info("Discover Strategy 2: Popularity across eras...")
            era_pop_ids = self.discover_by_popularity(
                pages_per_era=pages_per_era,
                min_vote_count=15,
                target_count=target_count,
            )
            all_candidate_ids.update(era_pop_ids)
            logger.info("Candidates after Strategy 2: %d", len(all_candidate_ids))

        # Strategy 3: Top-rated across eras
        if len(all_candidate_ids) < target_count:
            logger.info("Discover Strategy 3: Top-rated across eras...")
            era_rate_ids = self.discover_by_rating(
                pages_per_era=6,
                min_vote_count=35,
                min_rating=6.5,
                target_count=target_count,
            )
            all_candidate_ids.update(era_rate_ids)
            logger.info("Candidates after Strategy 3: %d", len(all_candidate_ids))

        # Strategy 4: Genre-based discovery
        if len(all_candidate_ids) < target_count:
            logger.info("Discover Strategy 4: Genre-based discovery (popularity)...")
            genre_ids = self.discover_by_genres(
                pages_per_genre=pages_per_genre,
                min_vote_count=15,
                sort_by="popularity.desc",
            )
            all_candidate_ids.update(genre_ids)
            logger.info("Candidates after Strategy 4 (popularity): %d", len(all_candidate_ids))

        if len(all_candidate_ids) < target_count:
            logger.info("Discover Strategy 4b: Genre-based discovery (rating)...")
            genre_rate_ids = self.discover_by_genres(
                pages_per_genre=max(4, pages_per_genre // 2),
                min_vote_count=30,
                sort_by="vote_average.desc",
            )
            all_candidate_ids.update(genre_rate_ids)
            logger.info("Candidates after Strategy 4b (rating): %d", len(all_candidate_ids))

        # Strategy 5: Recent air dates
        if len(all_candidate_ids) < target_count:
            logger.info("Discover Strategy 5: Recent & current air dates...")
            recent_ids = self.discover_recent_air_dates(pages=15, min_vote_count=8)
            all_candidate_ids.update(recent_ids)
            logger.info("Candidates after Strategy 5: %d", len(all_candidate_ids))

        return list(all_candidate_ids)

    # ------------------------------------------------------------------
    # Incremental changes sync
    # ------------------------------------------------------------------

    def sync_changed_series(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Fetch recently changed TV series — mirrors sync_changed_movies.

        Returns a list of full series detail dicts for series whose
        metadata changed during the given date window.
        """
        start_date, end_date = self.tmdb._change_date_range(start_date, end_date)

        processed_ids: set[int] = set()
        series_list: list[dict] = []
        skipped = 0
        page = 1
        total_pages = 1

        while page <= total_pages:
            try:
                data = self.safe_get(
                    "/tv/changes",
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "page": page,
                    },
                )
            except TMDBNotFoundError:
                skipped += 1
                logger.info("Skipped TV changes page: %d (404 error)", page)
                page += 1
                continue
            except TMDBRequestError as e:
                skipped += 1
                logger.warning("Skipped TV changes page: %d (%s error)", page, e.status_code)
                page += 1
                continue

            total_pages = data.get("total_pages", 1) or 1

            for item in data.get("results", []):
                series_id = item.get("id")

                if series_id is None:
                    skipped += 1
                    continue

                int_id = int(series_id)
                if int_id in processed_ids:
                    continue

                processed_ids.add(int_id)

                try:
                    series_list.append(self.fetch_series_details(int_id))
                except TMDBNotFoundError:
                    skipped += 1
                    logger.debug("Skipped missing series: %d", int_id)
                except TMDBRequestError as e:
                    skipped += 1
                    logger.debug("Skipped series: %d (%s error)", int_id, e.status_code)
                except Exception as e:
                    skipped += 1
                    logger.debug("Skipped series: %d (%s)", int_id, type(e).__name__)

            page += 1

        logger.info(
            "TV sync complete: %d checked, %d fetched, %d skipped",
            len(processed_ids),
            len(series_list),
            skipped,
        )

        return series_list

