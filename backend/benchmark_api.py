import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests


BASE_URL = "http://127.0.0.1:8000"
RESULTS_FILE = Path(__file__).resolve().parent / "api_benchmark_results.json"
RUN_COUNT = 10
WARMUP_RUNS = 1
REQUEST_TIMEOUT_SECONDS = 20

MOVIES = [
    "Jurassic World",
    "John Wick",
    "Interstellar",
    "The Meg",
    "Inception",
]


def elapsed_ms(start_time):
    return (time.perf_counter() - start_time) * 1000


# URL-encode movie titles so spaces, apostrophes, and punctuation survive routing.
def recommendation_url(movie_title):
    return f"{BASE_URL}/recommend/{quote(movie_title, safe='')}"


# Perform one real HTTP request and measure network/server latency separately
# from client-side JSON parsing latency.
def benchmark_once(movie_title):
    url = recommendation_url(movie_title)

    request_start = time.perf_counter()
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    http_latency_ms = elapsed_ms(request_start)

    json_start = time.perf_counter()
    payload = response.json()
    json_parse_ms = elapsed_ms(json_start)

    validate_response(movie_title, response, payload)

    return {
        "http_latency_ms": http_latency_ms,
        "json_parse_ms": json_parse_ms,
        "total_latency_ms": http_latency_ms + json_parse_ms,
        "status_code": response.status_code,
    }


def validate_response(movie_title, response, payload):
    if response.status_code != 200:
        raise ValueError(
            f"{movie_title}: expected HTTP 200, got {response.status_code}"
        )

    if set(payload.keys()) != {"movie", "recommendations"}:
        raise ValueError(
            f"{movie_title}: response must contain only movie and recommendations"
        )

    recommendations = payload.get("recommendations")

    if not isinstance(recommendations, list):
        raise ValueError(f"{movie_title}: recommendations must be a list")

    if len(recommendations) != 10:
        raise ValueError(
            f"{movie_title}: expected 10 recommendations, got {len(recommendations)}"
        )


# Discard the first request per movie so connection setup and cache warm-up do
# not skew the reported statistics.
def benchmark_movie(movie_title):
    runs = []
    failed_requests = 0

    for run_number in range(1, RUN_COUNT + 1):
        try:
            timings = benchmark_once(movie_title)
            timings["run"] = run_number
            timings["warmup"] = run_number <= WARMUP_RUNS
            runs.append(timings)
        except requests.ConnectionError:
            raise
        except (
            requests.RequestException,
            ValueError,
            json.JSONDecodeError,
        ) as e:
            failed_requests += 1
            runs.append({
                "run": run_number,
                "warmup": run_number <= WARMUP_RUNS,
                "error": str(e),
            })

    measured_runs = [
        run
        for run in runs[WARMUP_RUNS:]
        if "total_latency_ms" in run
    ]

    return {
        "movie": movie_title,
        "runs": runs,
        "failed_requests": failed_requests,
        "statistics": summarize_runs(measured_runs),
    }


def summarize_runs(runs):
    if not runs:
        return None

    return {
        "http_latency_ms": summarize_values(
            [run["http_latency_ms"] for run in runs]
        ),
        "json_parse_ms": summarize_values(
            [run["json_parse_ms"] for run in runs]
        ),
        "total_latency_ms": summarize_values(
            [run["total_latency_ms"] for run in runs]
        ),
    }


def summarize_values(values):
    return {
        "minimum": min(values),
        "maximum": max(values),
        "average": statistics.mean(values),
        "median": statistics.median(values),
        "standard_deviation": (
            statistics.stdev(values) if len(values) > 1 else 0.0
        ),
    }


def build_summary(results):
    movie_averages = {
        result["movie"]: result["statistics"]["total_latency_ms"]["average"]
        for result in results
        if result["statistics"] is not None
    }
    failed_requests = sum(result["failed_requests"] for result in results)

    if not movie_averages:
        return {
            "overall_average_api_latency_ms": None,
            "fastest_movie": None,
            "slowest_movie": None,
            "failed_requests": failed_requests,
        }

    fastest_movie = min(movie_averages, key=movie_averages.get)
    slowest_movie = max(movie_averages, key=movie_averages.get)

    return {
        "overall_average_api_latency_ms": statistics.mean(movie_averages.values()),
        "fastest_movie": {
            "movie": fastest_movie,
            "average_ms": movie_averages[fastest_movie],
        },
        "slowest_movie": {
            "movie": slowest_movie,
            "average_ms": movie_averages[slowest_movie],
        },
        "failed_requests": failed_requests,
    }


def print_movie_result(result):
    print("====================================================")
    print(f"Movie: {result['movie']}")
    print()

    if result["statistics"] is None:
        print("No successful measured requests.")
        print("====================================================")
        print()
        return

    total = result["statistics"]["total_latency_ms"]
    http = result["statistics"]["http_latency_ms"]
    json_parse = result["statistics"]["json_parse_ms"]

    print("API latency (HTTP request + JSON parsing):")
    print_stats(total)
    print()
    print("HTTP request latency:")
    print_stats(http)
    print()
    print("JSON parsing time:")
    print_stats(json_parse)
    print()
    print("Failed requests:", result["failed_requests"])
    print("====================================================")
    print()


def print_stats(stats):
    print(f"Minimum: {stats['minimum']:.2f} ms")
    print(f"Maximum: {stats['maximum']:.2f} ms")
    print(f"Average: {stats['average']:.2f} ms")
    print(f"Median: {stats['median']:.2f} ms")
    print(f"Standard deviation: {stats['standard_deviation']:.2f} ms")


def print_summary(summary):
    print("====================================================")
    print()
    print("Overall average API latency:", format_optional_ms(
        summary["overall_average_api_latency_ms"]
    ))

    if summary["fastest_movie"]:
        print(
            "Fastest movie:",
            summary["fastest_movie"]["movie"],
            f"({summary['fastest_movie']['average_ms']:.2f} ms)",
        )

    if summary["slowest_movie"]:
        print(
            "Slowest movie:",
            summary["slowest_movie"]["movie"],
            f"({summary['slowest_movie']['average_ms']:.2f} ms)",
        )

    print("Number of failed requests:", summary["failed_requests"])
    print()
    print("====================================================")


def format_optional_ms(value):
    return "n/a" if value is None else f"{value:.2f} ms"


def save_results(results, summary):
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "run_count": RUN_COUNT,
        "warmup_requests_discarded": WARMUP_RUNS,
        "movies": MOVIES,
        "benchmarks": results,
        "summary": summary,
    }

    with RESULTS_FILE.open("w", encoding="utf-8") as results_file:
        json.dump(output, results_file, indent=2)


def main():
    results = []

    try:
        for movie_title in MOVIES:
            result = benchmark_movie(movie_title)
            results.append(result)
            print_movie_result(result)
    except requests.ConnectionError:
        print(
            "FastAPI server is not running at "
            f"{BASE_URL}. Start the backend server, then run this benchmark again."
        )
        return 1

    summary = build_summary(results)
    print_summary(summary)
    save_results(results, summary)
    print()
    print("Saved:", RESULTS_FILE)

    return 0


if __name__ == "__main__":
    sys.exit(main())
