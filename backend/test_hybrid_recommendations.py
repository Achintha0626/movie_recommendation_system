from app import dataframe, hybrid_ranking_service, indices


TEST_MOVIES = [
    "Jurassic World",
    "The Meg",
    "John Wick",
    "Interstellar",
]


def print_recommendations(movie_title):
    if movie_title not in indices:
        print(f"{movie_title} | not found | Movie not found")
        return

    selected_index = int(indices[movie_title])
    recommendations = hybrid_ranking_service.recommend(
        selected_index,
        limit=10,
    )

    print(movie_title)
    for recommendation in recommendations:
        title = dataframe["original_title"].iloc[recommendation["index"]]
        reasons = ", ".join(recommendation["reasons"])
        print(f"{title} | {recommendation['match_score']} | {reasons}")


if __name__ == "__main__":
    for test_movie in TEST_MOVIES:
        print_recommendations(test_movie)
