"""Tests for TV series endpoints and recommendation service.

Run with:
    python -m pytest test_tv_endpoints.py -v

These tests verify the TV pipeline integration without modifying any
movie artifacts.
"""

import os
import sys

# Ensure backend directory is on sys.path for service imports.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app.

    Uses module scope so the app (and artifacts) are loaded once.
    """
    from app import app
    return TestClient(app)


# ==================================================================
# Movie endpoints — verify no regressions
# ==================================================================

class TestMovieEndpointsUnchanged:
    """Existing movie endpoints must continue working."""

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_movies_list(self, client):
        response = client.get("/movies")
        assert response.status_code == 200
        titles = response.json()
        assert isinstance(titles, list)
        assert len(titles) > 0

    def test_movie_search(self, client):
        response = client.get("/search", params={"query": "Jurassic"})
        assert response.status_code == 200
        results = response.json()["results"]
        assert isinstance(results, list)

    def test_movie_search_empty(self, client):
        response = client.get("/search", params={"query": ""})
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_genres(self, client):
        response = client.get("/genres")
        assert response.status_code == 200
        genres = response.json()["genres"]
        assert "All" in genres


# ==================================================================
# TV recommendation service — unit-level checks
# ==================================================================

class TestTVRecommendationService:
    """Verify the TV recommendation service loads and works correctly."""

    def test_service_loaded(self):
        from app import tv_available, tv_recommendation_service
        # May be True or False depending on whether artifacts exist.
        if not tv_available:
            pytest.skip("TV artifacts not available")
        assert tv_recommendation_service.available

    def test_catalogue_not_empty(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")
        assert len(tv_recommendation_service.catalogue) > 0

    def test_id_index_populated(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")
        assert len(tv_recommendation_service.id_to_index) > 0

    def test_embeddings_shape_matches_catalogue(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")
        assert tv_recommendation_service.embeddings.shape[0] == len(
            tv_recommendation_service.catalogue
        )

    def test_recommend_excludes_self(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        # Pick the first series ID in the catalogue.
        first_id = next(iter(tv_recommendation_service.id_to_index))
        results = tv_recommendation_service.recommend(first_id, limit=5)

        # The query series must not appear in its own results.
        result_ids = {r["id"] for r in results}
        assert first_id not in result_ids

    def test_recommend_sorted_by_similarity(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        first_id = next(iter(tv_recommendation_service.id_to_index))
        results = tv_recommendation_service.recommend(first_id, limit=10)

        if len(results) >= 2:
            scores = [r["similarity_score"] for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_recommend_unknown_id_returns_empty(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        results = tv_recommendation_service.recommend(999999999, limit=5)
        assert results == []

    def test_search_returns_matches(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        # Use the first series name from the catalogue.
        first_name = tv_recommendation_service.series_names[0]
        # Search for the first 3 characters.
        query = first_name[:3]
        results = tv_recommendation_service.search(query, limit=5)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_search_empty_query(self):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        results = tv_recommendation_service.search("", limit=5)
        assert results == []


# ==================================================================
# TV API endpoints
# ==================================================================

class TestTVEndpoints:
    """Test the TV REST endpoints through the FastAPI test client."""

    def test_tv_list(self, client):
        response = client.get("/tv")
        if response.status_code == 503:
            pytest.skip("TV artifacts not available")
        assert response.status_code == 200
        body = response.json()
        assert "results" in body
        assert "page" in body
        assert "total" in body
        assert "total_pages" in body
        assert isinstance(body["results"], list)

    def test_tv_list_pagination(self, client):
        response = client.get("/tv", params={"page": 1, "page_size": 5})
        if response.status_code == 503:
            pytest.skip("TV artifacts not available")
        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert len(body["results"]) <= 5

    def test_tv_list_invalid_page_size(self, client):
        response = client.get("/tv", params={"page_size": 0})
        assert response.status_code == 422  # validation error

    def test_tv_search(self, client):
        response = client.get("/tv/search", params={"query": "the"})
        if response.status_code == 503:
            pytest.skip("TV artifacts not available")
        assert response.status_code == 200
        assert "results" in response.json()

    def test_tv_search_empty(self, client):
        response = client.get("/tv/search", params={"query": ""})
        if response.status_code == 503:
            pytest.skip("TV artifacts not available")
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_tv_trending(self, client):
        response = client.get("/tv/trending")
        # May fail if TMDB key is invalid, but should not be 500.
        assert response.status_code in (200, 502, 503)
        if response.status_code == 200:
            assert "results" in response.json()

    def test_tv_recommend_known_id(self, client):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        first_id = next(iter(tv_recommendation_service.id_to_index))
        response = client.get(f"/tv/recommend/{first_id}")
        assert response.status_code == 200
        body = response.json()
        assert "recommendations" in body
        assert body["series_id"] == first_id
        assert isinstance(body["recommendations"], list)

        # Query series must not appear in its own recommendations.
        for rec in body["recommendations"]:
            assert rec["id"] != first_id

    def test_tv_recommend_unknown_id(self, client):
        response = client.get("/tv/recommend/999999999")
        if response.status_code == 503:
            pytest.skip("TV artifacts not available")
        assert response.status_code == 404

    def test_tv_details_known_id(self, client):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        first_id = next(iter(tv_recommendation_service.id_to_index))
        response = client.get(f"/tv/{first_id}")
        # Should be 200 if TMDB key is valid, 502/503 otherwise.
        assert response.status_code in (200, 502, 503)
        if response.status_code == 200:
            body = response.json()
            assert "id" in body
            assert "name" in body

    def test_tv_details_not_found(self, client):
        response = client.get("/tv/999999999")
        # TMDB should return 404 for this fake ID.
        assert response.status_code in (404, 502, 503)

    def test_static_routes_not_intercepted(self, client):
        """Verify /tv/search and /tv/trending are not caught by /tv/{series_id}."""
        search_resp = client.get("/tv/search", params={"query": "test"})
        # Should NOT be a 422 validation error from trying to parse
        # "search" as an integer series_id.
        assert search_resp.status_code != 422

        trending_resp = client.get("/tv/trending")
        assert trending_resp.status_code != 422

    def test_recommend_limit_parameter(self, client):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        first_id = next(iter(tv_recommendation_service.id_to_index))
        response = client.get(
            f"/tv/recommend/{first_id}", params={"limit": 3}
        )
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) <= 3


# ==================================================================
# Recommendation metadata fields
# ==================================================================

class TestRecommendationMetadata:
    """Verify that recommendation results contain the expected fields."""

    def test_recommendation_fields(self, client):
        from app import tv_available, tv_recommendation_service
        if not tv_available:
            pytest.skip("TV artifacts not available")

        first_id = next(iter(tv_recommendation_service.id_to_index))
        response = client.get(f"/tv/recommend/{first_id}")
        assert response.status_code == 200

        recs = response.json()["recommendations"]
        if not recs:
            pytest.skip("No recommendations returned")

        rec = recs[0]
        expected_fields = {
            "id", "name", "overview", "poster_url", "backdrop_url",
            "first_air_date", "genres", "vote_average", "popularity",
            "similarity_score", "match_score",
        }
        assert expected_fields.issubset(set(rec.keys()))
        assert isinstance(rec["similarity_score"], float)
        assert isinstance(rec["match_score"], int)
        assert rec["similarity_score"] != rec.get("vote_average")
