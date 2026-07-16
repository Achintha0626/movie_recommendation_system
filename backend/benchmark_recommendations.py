import json
import statistics
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import app as production_app


BASE_DIR = Path(__file__).resolve().parent
RESULTS_FILE = BASE_DIR / "benchmark_results.json"
EMBEDDING_METADATA_FILE = BASE_DIR / "dumped_obj" / "embedding_metadata.json"
RUN_COUNT = 10
WARMUP_RUNS = 1

BENCHMARK_MOVIES = [
    "Jurassic World",
    "John Wick",
    "Interstellar",
    "The Meg",
    "Harry Potter and the Sorcerer's Stone",
    "Avengers: Endgame",
    "The Dark Knight",
    "Inception",
    "Titanic",
    "Alien",
]

TITLE_ALIASES = {
    "Harry Potter and the Sorcerer's Stone": (
        "Harry Potter and the Philosopher's Stone"
    ),
}

PHASES = [
    "metadata_similarity_ms",
    "semantic_similarity_ms",
    "hybrid_ranking_ms",
    "response_generation_ms",
    "total_ms",
]


class PhaseTimer:

    def __init__(self):
        self.timings = {
            "metadata_similarity_ms": 0.0,
            "semantic_similarity_ms": 0.0,
            "ranking_total_ms": 0.0,
        }

    def measure(self, name, func, *args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        self.timings[name] += elapsed_ms(start)
        return result


def elapsed_ms(start_time):
    return (time.perf_counter() - start_time) * 1000


# Wrap the live production services so app.recommend() still runs normally.
@contextmanager
def instrument_recommendation_pipeline(timer):
    ranking_service = production_app.hybrid_ranking_service
    semantic_service = production_app.semantic_similarity_service

    original_ranking = ranking_service.recommend
    original_metadata = ranking_service._top_metadata_scores
    original_semantic = semantic_service.similarity_scores

    def timed_ranking(*args, **kwargs):
        return timer.measure("ranking_total_ms", original_ranking, *args, **kwargs)

    def timed_metadata(*args, **kwargs):
        return timer.measure(
            "metadata_similarity_ms",
            original_metadata,
            *args,
            **kwargs,
        )

    def timed_semantic(*args, **kwargs):
        return timer.measure(
            "semantic_similarity_ms",
            original_semantic,
            *args,
            **kwargs,
        )

    ranking_service.recommend = timed_ranking
    ranking_service._top_metadata_scores = timed_metadata
    semantic_service.similarity_scores = timed_semantic

    try:
        yield
    finally:
        ranking_service.recommend = original_ranking
        ranking_service._top_metadata_scores = original_metadata
        semantic_service.similarity_scores = original_semantic


# Resolve benchmark inputs to exact catalogue titles without changing production lookup.
def resolve_title(requested_title):
    if requested_title in production_app.indices:
        return requested_title

    alias = TITLE_ALIASES.get(requested_title)
    if alias and alias in production_app.indices:
        return alias

    return requested_title


# Run one recommendation through the production FastAPI handler and derive phase times.
def benchmark_once(movie_title):
    timer = PhaseTimer()

    with instrument_recommendation_pipeline(timer):
        start = time.perf_counter()
        response = production_app.recommend(movie_title)
        total_ms = elapsed_ms(start)

    if isinstance(response, dict) and response.get("error"):
        raise ValueError(response["error"])

    ranking_total_ms = timer.timings["ranking_total_ms"]
    metadata_ms = timer.timings["metadata_similarity_ms"]
    semantic_ms = timer.timings["semantic_similarity_ms"]
    hybrid_ms = max(0.0, ranking_total_ms - metadata_ms - semantic_ms)
    response_ms = max(0.0, total_ms - ranking_total_ms)

    return {
        "metadata_similarity_ms": metadata_ms,
        "semantic_similarity_ms": semantic_ms,
        "hybrid_ranking_ms": hybrid_ms,
        "response_generation_ms": response_ms,
        "total_ms": total_ms,
    }


# Discard the first run for each movie so caches and imports settle.
def benchmark_movie(requested_title):
    benchmark_title = resolve_title(requested_title)
    runs = []

    for run_number in range(RUN_COUNT):
        timings = benchmark_once(benchmark_title)
        timings["run"] = run_number + 1
        timings["warmup"] = run_number < WARMUP_RUNS
        runs.append(timings)

    measured_runs = runs[WARMUP_RUNS:]

    return {
        "requested_title": requested_title,
        "benchmark_title": benchmark_title,
        "runs": runs,
        "statistics": summarize_runs(measured_runs),
    }


# Summarize every measured phase using milliseconds as the common unit.
def summarize_runs(runs):
    summary = {}

    for phase in PHASES:
        values = [run[phase] for run in runs]

        summary[phase] = {
            "minimum": min(values),
            "maximum": max(values),
            "average": statistics.mean(values),
            "median": statistics.median(values),
            "standard_deviation": (
                statistics.stdev(values) if len(values) > 1 else 0.0
            ),
        }

    return summary


def load_embedding_metadata():
    if not EMBEDDING_METADATA_FILE.exists():
        return {}

    with EMBEDDING_METADATA_FILE.open("r", encoding="utf-8") as metadata_file:
        return json.load(metadata_file)


def benchmark_context():
    embedding_metadata = load_embedding_metadata()
    embeddings = production_app.semantic_similarity_service.embeddings

    return {
        "movie_count": len(production_app.dataframe),
        "embedding_count": int(embeddings.shape[0]),
        "embedding_dimension": int(embeddings.shape[1]),
        "metadata_similarity_shape": list(production_app.sig.shape),
        "model": embedding_metadata.get("model", "unknown"),
    }


# Print a compact block for each movie with full statistical detail underneath.
def print_movie_result(result):
    print("====================================================")
    print(f"Movie: {result['requested_title']}")

    if result["benchmark_title"] != result["requested_title"]:
        print(f"Catalogue title: {result['benchmark_title']}")

    print()
    print_phase("Metadata Similarity", result, "metadata_similarity_ms")
    print_phase("Semantic Similarity", result, "semantic_similarity_ms")
    print_phase("Hybrid Ranking", result, "hybrid_ranking_ms")
    print_phase("Response Generation", result, "response_generation_ms")
    print_phase("Total", result, "total_ms")
    print("====================================================")
    print()


def print_phase(label, result, phase):
    stats = result["statistics"][phase]
    print(f"{label}:")
    print(f"{stats['average']:.2f} ms")
    print(
        "Minimum: "
        f"{stats['minimum']:.2f} ms | "
        "Maximum: "
        f"{stats['maximum']:.2f} ms | "
        "Median: "
        f"{stats['median']:.2f} ms | "
        "Standard deviation: "
        f"{stats['standard_deviation']:.2f} ms"
    )
    print()


def print_dataset_context(context):
    print("Movie count:", context["movie_count"])
    print("Embedding count:", context["embedding_count"])
    print("Embedding dimension:", context["embedding_dimension"])
    print("Metadata similarity matrix shape:", context["metadata_similarity_shape"])
    print()


# Compute the final latency summary from per-movie average totals.
def build_summary(results):
    movie_averages = {
        result["requested_title"]: result["statistics"]["total_ms"]["average"]
        for result in results
    }
    fastest_movie = min(movie_averages, key=movie_averages.get)
    slowest_movie = max(movie_averages, key=movie_averages.get)
    overall_average = statistics.mean(movie_averages.values())

    return {
        "average_recommendation_latency": movie_averages,
        "fastest_movie": {
            "title": fastest_movie,
            "average_ms": movie_averages[fastest_movie],
        },
        "slowest_movie": {
            "title": slowest_movie,
            "average_ms": movie_averages[slowest_movie],
        },
        "overall_average_ms": overall_average,
    }


def print_summary(summary):
    print("====================================================")
    print()
    print("Average recommendation latency")

    for movie_title, average_ms in summary["average_recommendation_latency"].items():
        print(f"{movie_title}: {average_ms:.2f} ms")

    print()
    print(
        "Fastest movie:",
        summary["fastest_movie"]["title"],
        f"({summary['fastest_movie']['average_ms']:.2f} ms)",
    )
    print(
        "Slowest movie:",
        summary["slowest_movie"]["title"],
        f"({summary['slowest_movie']['average_ms']:.2f} ms)",
    )
    print("Overall average:", f"{summary['overall_average_ms']:.2f} ms")
    print()
    print("====================================================")


def save_results(context, results, summary):
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_size": context["movie_count"],
        "model": context["model"],
        "movie_count": context["movie_count"],
        "embedding_count": context["embedding_count"],
        "embedding_dimension": context["embedding_dimension"],
        "metadata_similarity_shape": context["metadata_similarity_shape"],
        "run_count": RUN_COUNT,
        "warmup_runs_discarded": WARMUP_RUNS,
        "benchmarks": results,
        "summary": summary,
    }

    with RESULTS_FILE.open("w", encoding="utf-8") as results_file:
        json.dump(output, results_file, indent=2)


def main():
    context = benchmark_context()
    results = []

    print_dataset_context(context)

    for movie_title in BENCHMARK_MOVIES:
        result = benchmark_movie(movie_title)
        results.append(result)
        print_movie_result(result)

    summary = build_summary(results)
    print_summary(summary)
    save_results(context, results, summary)
    print()
    print("Saved:", RESULTS_FILE)


if __name__ == "__main__":
    main()
