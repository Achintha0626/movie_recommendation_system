"""Comprehensive unit and scale tests for CineMatch TV Series pipeline.

Covers:
- Discovery pagination across strategies
- Deduplication strictly by TMDB ID
- Safe handling of missing metadata and transient API errors/rate-limits
- Embedding dimensions (N, 384) and artifact separation
- Recommendation quality, search ranking, and hybrid scoring
- Batch catalogue upserting and dataset integrity

All TMDB API calls are mocked; no live network calls are made.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from services.tmdb_service import TMDBNotFoundError, TMDBRequestError
from services.tv_dataset_service import TV_SCHEMA_COLUMNS, TVDatasetService
from services.tv_embedding_service import TVEmbeddingService
from services.tv_recommendation_service import TVRecommendationService
from services.tv_tmdb_service import TV_GENRES, TVTMDBService


# ======================================================================
# Test Discovery Strategies & Pagination
# ======================================================================

class TestTVDiscoveryPagination:
    """Test pagination across all TMDB discovery strategies with mocked responses."""

    def test_fetch_source_series_pagination(self):
        mock_tmdb = MagicMock()
        mock_tmdb.get.side_effect = lambda endpoint, params: {
            "page": params.get("page", 1),
            "total_pages": 3,
            "results": [
                {"id": abs(hash(endpoint)) % 100000 + params.get("page", 1) * 10 + i}
                for i in range(5)
            ],
        }

        service = TVTMDBService(tmdb=mock_tmdb)
        series_ids = service.fetch_source_series(pages_per_source=2)

        # 4 source endpoints * 2 pages * 5 results = 40 items (all unique IDs)
        assert len(series_ids) == 40
        assert all(isinstance(sid, int) for sid in series_ids)

    def test_discover_by_popularity_bounded_pagination(self):
        mock_tmdb = MagicMock()

        def mock_get(endpoint, params):
            page = params.get("page", 1)
            # Simulate only 2 pages available
            return {
                "page": page,
                "total_pages": 2,
                "results": [{"id": page * 100 + i} for i in range(3)],
            }

        mock_tmdb.get.side_effect = mock_get
        service = TVTMDBService(tmdb=mock_tmdb)

        eras = [(2020, 2024)]
        # Request 5 pages, but total_pages is 2 -> should terminate after page 2
        discovered = service.discover_by_popularity(
            pages_per_era=5,
            eras=eras,
            min_vote_count=10,
        )

        assert len(discovered) == 6  # 2 pages * 3 results
        assert discovered == {100, 101, 102, 200, 201, 202}

    def test_discover_by_rating_vote_threshold(self):
        mock_tmdb = MagicMock()
        recorded_params = []

        def mock_get(endpoint, params):
            recorded_params.append(params.copy())
            return {
                "page": 1,
                "total_pages": 1,
                "results": [{"id": 555}],
            }

        mock_tmdb.get.side_effect = mock_get
        service = TVTMDBService(tmdb=mock_tmdb)

        eras = [(2010, 2015)]
        service.discover_by_rating(
            pages_per_era=1,
            eras=eras,
            min_vote_count=50,
            min_rating=7.5,
        )

        assert len(recorded_params) == 1
        req = recorded_params[0]
        assert req["sort_by"] == "vote_average.desc"
        assert req["vote_count.gte"] == 50
        assert req["vote_average.gte"] == 7.5

    def test_discover_multi_strategy_aggregation(self):
        mock_tmdb = MagicMock()

        call_count = 0
        def mock_get(endpoint, params):
            nonlocal call_count
            call_count += 1
            # Return distinct IDs per call
            return {
                "page": 1,
                "total_pages": 1,
                "results": [{"id": call_count * 10 + i} for i in range(2)],
            }

        mock_tmdb.get.side_effect = mock_get
        service = TVTMDBService(tmdb=mock_tmdb)

        candidates = service.discover_multi_strategy(
            target_count=50,
            include_sources=True,
            pages_per_era=1,
            pages_per_genre=1,
        )

        assert len(candidates) > 0
        assert len(candidates) == len(set(candidates))


# ======================================================================
# Test Deduplication Strictly by TMDB ID
# ======================================================================

class TestTVDeduplication:
    """Ensure deduplication uses TMDB series IDs, not titles or names."""

    def test_same_name_different_ids_preserved(self):
        """Two series with the identical name (e.g. remake or reboot) must both be preserved."""
        dataset_service = TVDatasetService()
        initial_df = pd.DataFrame([
            {
                "id": 101,
                "name": "Doctor Who",
                "original_name": "Doctor Who",
                "first_air_date": "1963-11-23",
                "overview": "Classic British sci-fi series",
            }
        ])

        new_series = [
            {
                "id": 202,
                "name": "Doctor Who",  # Same name!
                "original_name": "Doctor Who",
                "first_air_date": "2005-03-26",
                "overview": "Modern revival of British sci-fi",
            }
        ]

        with patch.object(dataset_service, "save_catalogue"):
            updated_df = dataset_service.update(initial_df, new_series)

        assert len(updated_df) == 2
        assert set(updated_df["id"].tolist()) == {101, 202}
        assert list(updated_df["name"].tolist()) == ["Doctor Who", "Doctor Who"]

    def test_duplicate_id_in_batch_deduplicated(self):
        """Repeated IDs across discovery runs must be deduplicated."""
        dataset_service = TVDatasetService()
        empty_df = pd.DataFrame(columns=TV_SCHEMA_COLUMNS)

        records = [
            {"id": 42, "name": "The Hitchhiker's Guide", "vote_average": 8.0},
            {"id": 42, "name": "The Hitchhiker's Guide (Dup)", "vote_average": 8.1},
            {"id": 99, "name": "Another Show", "vote_average": 7.0},
        ]

        with patch.object(dataset_service, "save_catalogue"):
            updated = dataset_service.update(empty_df, records)

        assert len(updated) == 2
        assert set(updated["id"].tolist()) == {42, 99}


# ======================================================================
# Test Missing Metadata & Error Handling
# ======================================================================

class TestTVMetadataAndResilience:
    """Handle missing descriptions, posters, ratings, timeouts, and rate limits."""

    def test_fetch_series_details_missing_fields_defaults(self):
        mock_tmdb = MagicMock()
        mock_tmdb.get.return_value = {
            "id": 8888,
            "name": "Bare Bones Show",
            # Missing: overview, poster_path, backdrop_path, genres, keywords, credits, etc.
        }

        service = TVTMDBService(tmdb=mock_tmdb)
        details = service.fetch_series_details(8888)

        assert details["id"] == 8888
        assert details["name"] == "Bare Bones Show"
        assert details["overview"] == ""
        assert details["poster_path"] == ""
        assert details["backdrop_path"] == ""
        assert details["genres"] == ""
        assert details["keywords"] == ""
        assert details["cast"] == ""
        assert details["created_by"] == ""
        assert details["vote_average"] == 0.0
        assert details["number_of_seasons"] == 0

    def test_safe_get_retries_on_rate_limit(self):
        mock_tmdb = MagicMock()
        # First call raises 429 rate limit, second call succeeds
        mock_tmdb.get.side_effect = [
            TMDBRequestError(429, "/tv/123"),
            {"id": 123, "name": "Recovered Show"},
        ]

        service = TVTMDBService(tmdb=mock_tmdb)
        with patch("time.sleep"):  # Speed up test
            data = service.safe_get("/tv/123", max_retries=3)

        assert data["id"] == 123
        assert mock_tmdb.get.call_count == 2

    def test_safe_get_raises_not_found_without_retry(self):
        mock_tmdb = MagicMock()
        mock_tmdb.get.side_effect = TMDBNotFoundError()

        service = TVTMDBService(tmdb=mock_tmdb)
        with pytest.raises(TMDBNotFoundError):
            service.safe_get("/tv/999999", max_retries=3)

        # 404 should not retry
        assert mock_tmdb.get.call_count == 1

    def test_fetch_series_details_batch_handles_failures(self):
        mock_tmdb = MagicMock()

        def mock_get(endpoint, params):
            if "101" in endpoint:
                return {"id": 101, "name": "Show 101"}
            elif "404" in endpoint:
                raise TMDBNotFoundError()
            elif "500" in endpoint:
                raise TMDBRequestError(500, endpoint)
            return {"id": 202, "name": "Show 202"}

        mock_tmdb.get.side_effect = mock_get
        service = TVTMDBService(tmdb=mock_tmdb)

        with patch("time.sleep"):
            results = service.fetch_series_details_batch(
                [101, 404, 500, 202],
                max_workers=2,
            )

        # 101 and 202 succeed, 404 and 500 safely skipped
        assert len(results) == 2
        result_ids = {r["id"] for r in results}
        assert result_ids == {101, 202}


# ======================================================================
# Test Embedding Generation & Artifact Separation
# ======================================================================

class TestTVEmbeddingGeneration:
    """Test text embedding formatting and vector dimensionality."""

    def test_embedding_texts_handles_nulls_cleanly(self):
        df = pd.DataFrame([
            {
                "name": "Dark",
                "genres": "Drama Mystery Sci-Fi",
                "keywords": "time travel wormhole",
                "tagline": "The beginning is the end",
                "overview": "A missing child sets four families on a frantic hunt for answers.",
            },
            {
                "name": "Missing Data Show",
                "genres": None,
                "keywords": np.nan,
                "tagline": "",
                "overview": None,
            },
        ])

        service = TVEmbeddingService()
        texts = service._build_embedding_texts(df)

        assert len(texts) == 2
        assert "Dark Drama Mystery" in texts[0]
        assert "time travel" in texts[0]
        assert texts[1].strip() == "Missing Data Show"

    def test_mock_embedding_shape_and_metadata(self, tmp_path):
        catalogue_file = tmp_path / "tv_catalogue.csv"
        embeddings_file = tmp_path / "tv_embeddings.pkl"
        metadata_file = tmp_path / "tv_metadata.json"

        df = pd.DataFrame([
            {"name": f"Show {i}", "overview": f"Overview {i}", "genres": "Drama"}
            for i in range(10)
        ])
        df.to_csv(catalogue_file, index=False)

        service = TVEmbeddingService(
            data_file=catalogue_file,
            embeddings_file=embeddings_file,
            metadata_file=metadata_file,
        )

        # Mock sentence transformer encoder
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(10, 384).astype(np.float32)
        mock_model.get_sentence_embedding_dimension.return_value = 384

        with patch.object(service, "load_model", return_value=mock_model):
            service.rebuild()

        assert embeddings_file.exists()
        assert metadata_file.exists()

        import joblib
        saved_emb = joblib.load(embeddings_file)
        assert saved_emb.shape == (10, 384)

        import json
        with metadata_file.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["series_count"] == 10
        assert meta["embedding_dimension"] == 384
        assert meta["model"] == "all-MiniLM-L6-v2"


# ======================================================================
# Test Recommendation & Full Catalogue Search
# ======================================================================

class TestTVRecommendationAndSearch:
    """Test normalized cosine similarity, candidate hybrid ranking, and search ranking."""

    @pytest.fixture
    def populated_service(self, tmp_path):
        catalogue_path = tmp_path / "tv_catalogue.csv"
        embeddings_path = tmp_path / "tv_semantic_embeddings.pkl"

        shows = [
            {
                "id": 1,
                "name": "Breaking Bad",
                "original_name": "Breaking Bad",
                "overview": "A chemistry teacher diagnosed with lung cancer turns to manufacturing methamphetamine.",
                "genres": "Drama Crime Thriller",
                "popularity": 120.0,
                "vote_average": 9.5,
                "vote_count": 14000,
                "poster_path": "/breaking.jpg",
                "backdrop_path": "/breaking_bg.jpg",
            },
            {
                "id": 2,
                "name": "Better Call Saul",
                "original_name": "Better Call Saul",
                "overview": "The trials and tribulations of criminal lawyer Jimmy McGill.",
                "genres": "Drama Crime",
                "popularity": 95.0,
                "vote_average": 8.9,
                "vote_count": 8000,
                "poster_path": "/saul.jpg",
                "backdrop_path": "/saul_bg.jpg",
            },
            {
                "id": 3,
                "name": "The Wire",
                "original_name": "The Wire",
                "overview": "The Baltimore drug scene, as seen through the eyes of law enforcement.",
                "genres": "Drama Crime Mystery",
                "popularity": 60.0,
                "vote_average": 9.0,
                "vote_count": 7000,
                "poster_path": "/wire.jpg",
                "backdrop_path": "/wire_bg.jpg",
            },
            {
                "id": 4,
                "name": "Friends",
                "original_name": "Friends",
                "overview": "Six young people living in New York City hang out at a coffee shop.",
                "genres": "Comedy Romance",
                "popularity": 110.0,
                "vote_average": 8.4,
                "vote_count": 12000,
                "poster_path": "/friends.jpg",
                "backdrop_path": "/friends_bg.jpg",
            },
        ]

        df = pd.DataFrame(shows)
        df.to_csv(catalogue_path, index=False)

        # Synthetic embeddings: Breaking Bad (1), Saul (2), Wire (3) close; Friends (4) distant
        emb = np.zeros((4, 384), dtype=np.float32)
        emb[0, :10] = [1.0, 0.9, 0.8, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # Breaking Bad
        emb[1, :10] = [0.9, 1.0, 0.8, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # Better Call Saul
        emb[2, :10] = [0.8, 0.7, 0.9, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # The Wire
        emb[3, :10] = [0.0, 0.0, 0.0, 0.0, 1.0, 0.9, 0.8, 0.0, 0.0, 0.0]  # Friends

        import joblib
        joblib.dump(emb, embeddings_path)

        service = TVRecommendationService(
            catalogue_path=catalogue_path,
            embeddings_path=embeddings_path,
        )
        assert service.load() is True
        return service

    def test_recommendation_excludes_query_series(self, populated_service):
        recs = populated_service.recommend(1, limit=3)
        assert len(recs) == 3
        # Query series ID (1) must never be in its own recommendations
        assert all(card["id"] != 1 for card in recs)

    def test_recommendation_ranking_and_scores(self, populated_service):
        recs = populated_service.recommend(1, limit=3)
        # Better Call Saul (2) and The Wire (3) should rank before Friends (4)
        top_id = recs[0]["id"]
        assert top_id in (2, 3)
        assert recs[-1]["id"] == 4

        # Scores should be sorted descending
        scores = [card["similarity_score"] for card in recs]
        assert scores == sorted(scores, reverse=True)

        for card in recs:
            assert 0 <= card["match_score"] <= 99
            assert "poster_url" in card
            assert "backdrop_url" in card

    def test_search_ranks_exact_and_popular_first(self, populated_service):
        # Query "Breaking"
        matches = populated_service.search("Breaking", limit=5)
        assert len(matches) >= 1
        assert matches[0]["name"] == "Breaking Bad"

        # Case-insensitive substring query "call"
        matches_call = populated_service.search("call", limit=5)
        assert len(matches_call) >= 1
        assert matches_call[0]["name"] == "Better Call Saul"

    def test_search_full_catalogue_empty_query(self, populated_service):
        matches = populated_service.search("", limit=5)
        assert matches == []
        matches_spaces = populated_service.search("   ", limit=5)
        assert matches_spaces == []
