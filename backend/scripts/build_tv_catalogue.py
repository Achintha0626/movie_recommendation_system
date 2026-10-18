"""Build (or incrementally update) the TV series catalogue and ML artifacts.

Usage examples:

    # Discover + populate + build embeddings (first run):
    python scripts/build_tv_catalogue.py --discover

    # Discover with more pages and a language filter:
    python scripts/build_tv_catalogue.py --discover --pages 3 --language en

    # Quick: just the popular/top-rated/on-the-air lists:
    python scripts/build_tv_catalogue.py --quick

    # Incremental: fetch recently changed series and update:
    python scripts/build_tv_catalogue.py --incremental

    # All three sources combined:
    python scripts/build_tv_catalogue.py --discover --quick --incremental

    # Rebuild embeddings only (after manual CSV edits):
    python scripts/build_tv_catalogue.py --embeddings-only

The script always rebuilds TV embeddings after any catalogue changes.
"""

import argparse
import os
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from services.tv_dataset_service import TVDatasetService
from services.tv_embedding_service import TVEmbeddingService
from services.tv_tmdb_service import TVTMDBService
from services.tmdb_service import TMDBNotFoundError, TMDBRequestError


BATCH_SIZE = 20


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build the CineMatch TV series catalogue and ML artifacts.",
    )

    source_group = parser.add_argument_group("data sources")
    source_group.add_argument(
        "--discover",
        action="store_true",
        help="Run multi-strategy discovery across eras, ratings, genres, and recent broadcasts.",
    )
    source_group.add_argument(
        "--quick",
        action="store_true",
        help="Fetch popular/top-rated/on-the-air/airing-today lists.",
    )
    source_group.add_argument(
        "--incremental",
        action="store_true",
        help="Fetch recently changed TV series (last 7 days).",
    )
    source_group.add_argument(
        "--embeddings-only",
        action="store_true",
        help="Skip TMDB fetching; only rebuild embeddings from the existing CSV.",
    )

    tuning_group = parser.add_argument_group("tuning")
    tuning_group.add_argument(
        "--target-count",
        type=int,
        default=4000,
        help="Target total candidate series to discover (default: 4000).",
    )
    tuning_group.add_argument(
        "--pages",
        type=int,
        default=5,
        help="Pages per discovery slot/era (default: 5).",
    )
    tuning_group.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent worker threads for detail fetching (default: 8).",
    )
    tuning_group.add_argument(
        "--min-votes",
        type=int,
        default=20,
        help="Minimum vote count for discovery (default: 20).",
    )
    tuning_group.add_argument(
        "--min-rating",
        type=float,
        default=5.0,
        help="Minimum vote average for discovery (default: 5.0).",
    )
    tuning_group.add_argument(
        "--language",
        type=str,
        default=None,
        help="Original language filter for discovery (e.g. en, ko, ja).",
    )
    tuning_group.add_argument(
        "--max-new",
        type=int,
        default=5000,
        help="Maximum number of new series to fetch details for per run (default: 5000).",
    )

    args = parser.parse_args()

    if not (args.discover or args.quick or args.incremental or args.embeddings_only):
        parser.error(
            "Choose at least one mode: --discover, --quick, --incremental, "
            "or --embeddings-only"
        )

    return args


def gather_candidate_ids(tv_tmdb, args):
    """Collect unique candidate TMDB series IDs using configured discovery strategies."""
    candidate_ids: set[int] = set()

    if args.quick:
        print("\n--- Fetching source lists (popular/top-rated/on-the-air/airing-today) ---")
        ids = tv_tmdb.fetch_source_series(pages_per_source=5)
        print(f"Source lists gathered: {len(ids)} unique series IDs")
        candidate_ids.update(ids)

    if args.discover:
        print(f"\n--- Running multi-strategy discovery (target: {args.target_count}, pages: {args.pages}) ---")
        ids = tv_tmdb.discover_multi_strategy(
            target_count=args.target_count,
            include_sources=not args.quick,
            pages_per_era=args.pages,
            pages_per_genre=max(4, args.pages),
        )
        print(f"Multi-strategy discovery gathered: {len(ids)} unique series IDs")
        candidate_ids.update(ids)

    return candidate_ids


def print_progress(completed: int, total: int, fetched: int, skipped: int):
    pct = (completed / total) * 100 if total > 0 else 0
    print(
        f"  Progress: {completed}/{total} ({pct:.1f}%) | "
        f"Fetched: {fetched} | Skipped/Failed: {skipped}"
    )


def fetch_series_details_batch(
    tv_tmdb,
    series_ids: list[int],
    max_new: int,
    workers: int = 8,
) -> list[dict]:
    """Fetch full details for candidate series IDs using concurrent workers."""
    ids_to_fetch = series_ids[:max_new]
    total = len(ids_to_fetch)
    print(f"\nFetching details for {total} new TV series using {workers} concurrent workers...")

    start_time = time.perf_counter()
    results = tv_tmdb.fetch_series_details_batch(
        ids_to_fetch,
        max_workers=workers,
        delay=0.03,
        on_progress=print_progress,
    )
    elapsed = time.perf_counter() - start_time
    rate = len(results) / elapsed if elapsed > 0 else 0
    print(f"Completed details fetch: {len(results)} series in {elapsed:.1f}s ({rate:.1f} series/s)")
    return results


def main():
    args = parse_args()

    tv_dataset = TVDatasetService()
    tv_embedding = TVEmbeddingService()

    # ------------------------------------------------------------------
    # Embeddings-only mode
    # ------------------------------------------------------------------
    if args.embeddings_only:
        print("Rebuilding TV embeddings from existing catalogue ...")
        tv_embedding.rebuild()
        validate_artifacts(tv_dataset, tv_embedding)
        return 0

    # ------------------------------------------------------------------
    # Normal mode: gather candidates → fetch details → update catalogue
    # ------------------------------------------------------------------
    tv_tmdb = TVTMDBService()
    existing_df = tv_dataset.load_catalogue()
    existing_ids = tv_dataset.get_existing_ids(existing_df)

    print(f"Existing TV series in catalogue: {len(existing_ids)}")

    all_series: list[dict] = []

    # --- Source lists + discovery ---
    if args.quick or args.discover:
        candidate_ids = gather_candidate_ids(tv_tmdb, args)
        new_ids = [sid for sid in candidate_ids if sid not in existing_ids]
        print(f"\nTotal candidate IDs discovered: {len(candidate_ids)}")
        print(f"New candidate IDs (not yet in catalogue): {len(new_ids)}")

        if new_ids:
            series = fetch_series_details_batch(
                tv_tmdb, new_ids, args.max_new, workers=args.workers
            )
            all_series.extend(series)

    # --- Incremental sync ---
    if args.incremental:
        print("\n--- Running incremental sync (recent changes) ---")
        changed_series = tv_tmdb.sync_changed_series()
        all_series.extend(changed_series)

    # --- Update catalogue ---
    if all_series:
        print(f"\nUpdating catalogue with {len(all_series)} series records...")
        updated_df = tv_dataset.update(existing_df, all_series)
        stats = tv_dataset.last_update_stats
        print(
            f"  Added: {stats['added']}, "
            f"Updated: {stats['updated']}, "
            f"Skipped: {stats['skipped']}"
        )
        print(f"Final catalogue size: {len(updated_df)} unique TV series")
    else:
        updated_df = existing_df
        print("\nNo new series to add.")

    # --- Rebuild embeddings ---
    print("\n--- Building TV semantic embeddings ---")
    tv_embedding.rebuild()

    # --- Validate ---
    validate_artifacts(tv_dataset, tv_embedding)

    return 0


def validate_artifacts(tv_dataset: TVDatasetService, tv_embedding: TVEmbeddingService):
    """Sanity check on the generated TV artifacts and memory footprints."""
    import json
    from pathlib import Path

    import joblib
    import numpy as np

    catalogue_path = tv_dataset.catalogue_file
    embeddings_path = tv_embedding.embeddings_file
    metadata_path = tv_embedding.metadata_file

    errors: list[str] = []

    if not catalogue_path.exists():
        errors.append(f"Missing catalogue: {catalogue_path}")
    if not embeddings_path.exists():
        errors.append(f"Missing embeddings: {embeddings_path}")
    if not metadata_path.exists():
        errors.append(f"Missing metadata: {metadata_path}")

    if errors:
        print("\nValidation FAILED:")
        for err in errors:
            print(f"  - {err}")
        return

    import pandas as pd

    df = pd.read_csv(catalogue_path)
    embeddings = joblib.load(embeddings_path)
    embeddings = np.asarray(embeddings, dtype=float)

    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)

    series_count = len(df)

    if embeddings.ndim != 2:
        errors.append("Embeddings must be a 2D matrix.")
    elif embeddings.shape[0] != series_count:
        errors.append(
            f"Embedding count ({embeddings.shape[0]}) does not match "
            f"catalogue rows ({series_count})."
        )
    elif embeddings.shape[1] != 384:
        errors.append(
            f"Expected embedding dimension 384, got {embeddings.shape[1]}"
        )

    if metadata.get("series_count") != series_count:
        errors.append(
            f"Metadata series_count ({metadata.get('series_count')}) "
            f"does not match catalogue ({series_count})."
        )

    # Check for duplicate TMDB IDs
    if "id" in df.columns:
        duplicate_ids = df["id"].dropna().astype(int)
        dup_count = duplicate_ids.duplicated().sum()
        if dup_count > 0:
            errors.append(f"{dup_count} duplicate TMDB IDs found.")

    if errors:
        print("\nValidation FAILED:")
        for err in errors:
            print(f"  - {err}")
    else:
        csv_size_mb = catalogue_path.stat().st_size / (1024 * 1024)
        emb_size_mb = embeddings_path.stat().st_size / (1024 * 1024)
        emb_mem_mb = embeddings.nbytes / (1024 * 1024)

        print("\n================ Validation PASSED ================")
        print(f"  Total Unique Series:   {series_count}")
        print(f"  Embedding Shape:       {embeddings.shape} (float32)")
        print(f"  Catalogue CSV Size:    {csv_size_mb:.2f} MB")
        print(f"  Embedding File Size:   {emb_size_mb:.2f} MB")
        print(f"  In-Memory Vectors:     {emb_mem_mb:.2f} MB")
        print(f"  Precomputed N×N:       NONE (vector dot product used for O(N) memory)")
        print(f"  Model:                 {metadata.get('model')}")
        print("===================================================")


if __name__ == "__main__":
    raise SystemExit(main())
