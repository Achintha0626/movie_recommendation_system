import time

from services.dataset_service import DatasetService
from services.similarity_service import SimilarityService
from services.tmdb_service import TMDBService


def main(start_date=None, end_date=None):
    start_time = time.perf_counter()
    similarity_rebuilt = False
    fatal_error = None

    tmdb = TMDBService()
    dataset = DatasetService()
    similarity = SimilarityService()

    try:
        old_df = dataset.load_dataframe()
        changed_movies = tmdb.sync_changed_movies(start_date, end_date)
        dataset.update(old_df, changed_movies)

        similarity.rebuild(verbose=False)
        similarity_rebuilt = True
    except Exception as e:
        fatal_error = e
    finally:
        total_runtime = time.perf_counter() - start_time
        movies_skipped = (
            tmdb.last_sync_stats["skipped"] +
            dataset.last_update_stats["skipped"]
        )

        print("Movies checked:", tmdb.last_sync_stats["checked"])
        print("Movies added:", dataset.last_update_stats["added"])
        print("Movies updated:", dataset.last_update_stats["updated"])
        print("Movies skipped:", movies_skipped)
        print("Similarity rebuilt:", similarity_rebuilt)
        print("Total runtime:", f"{total_runtime:.2f} seconds")

    if fatal_error is not None:
        raise fatal_error


if __name__ == "__main__":
    main()
