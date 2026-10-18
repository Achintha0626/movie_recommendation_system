"""TV series recommendation service.

Loads the TV catalogue and precomputed semantic embeddings once at
initialization, then provides recommendations using vectorized cosine
similarity.  Everything is keyed by TMDB series ID (not title) to handle
duplicate names safely.

This service is completely independent of the movie pipeline's artifacts.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
TV_DATA_DIR = BASE_DIR / "dumped_obj" / "tv"

TV_CATALOGUE_FILE = TV_DATA_DIR / "tv_catalogue.csv"
TV_EMBEDDINGS_FILE = TV_DATA_DIR / "tv_semantic_embeddings.pkl"

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_ORIGINAL_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

# Columns returned in recommendation and list results.
CARD_COLUMNS = [
    "id",
    "name",
    "overview",
    "poster_path",
    "backdrop_path",
    "first_air_date",
    "genres",
    "vote_average",
    "vote_count",
    "popularity",
    "number_of_seasons",
    "number_of_episodes",
    "status",
]


class TVRecommendationError(RuntimeError):
    """Raised when TV artifacts are invalid or inconsistent."""
    pass


class TVRecommendationService:
    """Provide TV series recommendations using precomputed embeddings.

    Designed to be instantiated once at app startup.  Subsequent calls to
    ``recommend``, ``search``, or ``list_series`` are fast lookups against
    the in-memory catalogue and embeddings.
    """

    def __init__(
        self,
        catalogue_path: Path | str = TV_CATALOGUE_FILE,
        embeddings_path: Path | str = TV_EMBEDDINGS_FILE,
    ):
        self.catalogue_path = Path(catalogue_path)
        self.embeddings_path = Path(embeddings_path)

        self.catalogue: pd.DataFrame = pd.DataFrame()
        self.embeddings: np.ndarray | None = None

        # TMDB series ID → DataFrame row index (int → int).
        self.id_to_index: dict[int, int] = {}

        # Series names for search (deduplicated, preserves insertion order).
        self.series_names: list[str] = []

        self._loaded = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load and validate TV artifacts.

        Returns True if artifacts were loaded successfully, False if they
        are missing (allowing the app to start without TV support).

        Raises ``TVRecommendationError`` if files exist but are corrupt
        or inconsistent.
        """
        if not self.catalogue_path.exists():
            logger.warning(
                "TV catalogue not found at %s — TV endpoints disabled.",
                self.catalogue_path,
            )
            return False

        if not self.embeddings_path.exists():
            logger.warning(
                "TV embeddings not found at %s — TV endpoints disabled.",
                self.embeddings_path,
            )
            return False

        try:
            self.catalogue = pd.read_csv(self.catalogue_path)
        except Exception as e:
            raise TVRecommendationError(
                f"Could not load TV catalogue: {self.catalogue_path}"
            ) from e

        if self.catalogue.empty:
            logger.warning("TV catalogue is empty — TV endpoints disabled.")
            return False

        try:
            raw_embeddings = joblib.load(self.embeddings_path)
            self.embeddings = np.asarray(raw_embeddings, dtype=float)
        except Exception as e:
            raise TVRecommendationError(
                f"Could not load TV embeddings: {self.embeddings_path}"
            ) from e

        self._validate()
        self._build_id_index()
        self._normalize_embeddings()

        self._loaded = True
        logger.info(
            "TV recommendation service loaded: %d series, embedding shape %s",
            len(self.catalogue),
            self.embeddings.shape,
        )
        return True

    def _normalize_embeddings(self) -> None:
        """Pre-compute L2-normalized embeddings for fast cosine dot products."""
        if self.embeddings is None:
            return
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.normalized_embeddings = (self.embeddings / norms).astype(np.float32)

    @property
    def available(self) -> bool:
        """Whether TV artifacts are loaded and ready to serve requests."""
        return self._loaded

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def recommend(
        self,
        series_id: int,
        limit: int = 10,
        use_hybrid_ranking: bool = True,
    ) -> list[dict]:
        """Return the top ``limit`` most similar TV series.

        Uses pre-normalized embeddings for fast cosine similarity search,
        followed by candidate hybrid re-ranking combining semantic similarity,
        genre overlap, and series popularity.
        """
        self._require_loaded()

        row_index = self.id_to_index.get(series_id)
        if row_index is None:
            return []

        scores = self._cosine_similarity_scores(row_index)

        # Retrieve top candidate pool by semantic similarity
        candidate_pool_size = max(50, limit * 3)
        candidate_pool_size = min(candidate_pool_size, len(scores) - 1)
        if candidate_pool_size <= 0:
            return []

        top_indices = np.argpartition(scores, -candidate_pool_size)[-candidate_pool_size:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        query_row = self.catalogue.iloc[row_index]
        query_genres = set(str(query_row.get("genres") or "").casefold().split())

        scored_candidates = []
        for cand_idx in top_indices:
            cand_idx = int(cand_idx)
            if cand_idx == row_index:
                continue

            sem_score = float(scores[cand_idx])
            if not np.isfinite(sem_score) or sem_score <= -1.0:
                continue

            if not use_hybrid_ranking:
                final_score = sem_score
            else:
                cand_row = self.catalogue.iloc[cand_idx]
                cand_genres = set(str(cand_row.get("genres") or "").casefold().split())

                # Genre overlap score (Jaccard)
                if query_genres and cand_genres:
                    genre_score = len(query_genres & cand_genres) / len(query_genres | cand_genres)
                else:
                    genre_score = 0.0

                # Popularity score (log scaled)
                cand_pop = float(cand_row.get("popularity") or 0.0)
                pop_score = min(1.0, np.log1p(max(0.0, cand_pop)) / 7.0)

                # Hybrid combination: 70% semantic, 15% genre overlap, 15% popularity
                final_score = (
                    0.70 * sem_score
                    + 0.15 * genre_score
                    + 0.15 * pop_score
                )

            scored_candidates.append((final_score, sem_score, cand_idx))

        # Sort descending by final score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        results: list[dict] = []
        for final_score, sem_score, cand_idx in scored_candidates[:limit]:
            card = self._series_card(cand_idx, similarity_score=final_score)
            card["semantic_score"] = round(sem_score, 4)
            results.append(card)

        return results

    # ------------------------------------------------------------------
    # Catalogue queries
    # ------------------------------------------------------------------

    def get_series_by_id(self, series_id: int) -> dict | None:
        """Return catalogue metadata for a single series, or None."""
        self._require_loaded()

        row_index = self.id_to_index.get(series_id)
        if row_index is None:
            return None

        return self._series_card(row_index)

    def list_series(self, page: int = 1, page_size: int = 20) -> dict:
        """Return a paginated list of TV series from the local catalogue."""
        self._require_loaded()

        total = len(self.catalogue)
        total_pages = max(1, -(-total // page_size))  # ceil division
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        end = start + page_size

        items = [
            self._series_card(idx)
            for idx in range(start, min(end, total))
        ]

        return {
            "results": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search the entire local TV catalogue by series name with ranked relevance."""
        self._require_loaded()

        normalized_query = query.strip().casefold()
        if not normalized_query:
            return []

        scored_matches: list[tuple[int, float, int, int]] = []

        for idx in range(len(self.catalogue)):
            row = self.catalogue.iloc[idx]
            name = str(row.get("name") or "").strip()
            orig_name = str(row.get("original_name") or "").strip()

            norm_name = name.casefold()
            norm_orig = orig_name.casefold()

            priority = 0
            # 1. Exact match
            if norm_name == normalized_query or norm_orig == normalized_query:
                priority = 4
            # 2. Prefix match
            elif norm_name.startswith(normalized_query) or norm_orig.startswith(normalized_query):
                priority = 3
            # 3. Word prefix match
            elif any(w.startswith(normalized_query) for w in norm_name.split()) or any(w.startswith(normalized_query) for w in norm_orig.split()):
                priority = 2
            # 4. Substring match
            elif normalized_query in norm_name or normalized_query in norm_orig:
                priority = 1

            if priority > 0:
                pop = float(row.get("popularity") or 0.0)
                votes = int(row.get("vote_count") or 0)
                scored_matches.append((priority, pop, votes, idx))

        # Rank by match priority descending, then popularity, then votes
        scored_matches.sort(
            key=lambda x: (x[0], x[1], x[2]),
            reverse=True,
        )

        return [
            self._series_card(idx)
            for _, _, _, idx in scored_matches[:limit]
        ]

    # ------------------------------------------------------------------
    # Internal: similarity
    # ------------------------------------------------------------------

    def _cosine_similarity_scores(self, row_index: int) -> np.ndarray:
        """Compute cosine similarity between one series and all others.

        Uses pre-normalized embedding matrix for a fast BLAS dot product.
        """
        if hasattr(self, "normalized_embeddings") and self.normalized_embeddings is not None:
            selected = self.normalized_embeddings[row_index]
            scores = self.normalized_embeddings @ selected
        else:
            selected = self.embeddings[row_index]
            selected_norm = np.linalg.norm(selected)
            all_norms = np.linalg.norm(self.embeddings, axis=1)
            denominator = selected_norm * all_norms

            with np.errstate(divide="ignore", invalid="ignore"):
                scores = np.divide(
                    self.embeddings @ selected,
                    denominator,
                    out=np.zeros(len(self.embeddings), dtype=float),
                    where=denominator != 0,
                )

        # Mark the query series so it cannot appear in results
        scores = scores.copy()
        scores[row_index] = -1.0
        return scores

    # ------------------------------------------------------------------
    # Internal: validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if self.embeddings is None:
            raise TVRecommendationError("TV embeddings were not loaded.")

        if self.embeddings.ndim != 2:
            raise TVRecommendationError(
                "TV embeddings must be a 2D matrix."
            )

        catalogue_rows = len(self.catalogue)
        embedding_rows = self.embeddings.shape[0]

        if catalogue_rows != embedding_rows:
            raise TVRecommendationError(
                f"TV embedding count ({embedding_rows}) does not match "
                f"catalogue row count ({catalogue_rows})."
            )

        if self.embeddings.shape[1] <= 0:
            raise TVRecommendationError(
                "TV embeddings must have at least one dimension."
            )

        if "id" not in self.catalogue.columns:
            raise TVRecommendationError(
                "TV catalogue is missing the 'id' column."
            )

    def _build_id_index(self) -> None:
        """Build TMDB ID → row index mapping, rejecting duplicates."""
        self.id_to_index = {}
        names: list[str] = []

        for row_index, series_id in self.catalogue["id"].items():
            if pd.isna(series_id):
                continue

            int_id = int(series_id)
            if int_id not in self.id_to_index:
                self.id_to_index[int_id] = int(row_index)

        # Build searchable name list (preserving catalogue order).
        name_col = "name"
        if name_col in self.catalogue.columns:
            names = list(
                dict.fromkeys(
                    self.catalogue[name_col].dropna().astype(str)
                )
            )

        self.series_names = names

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise TVRecommendationError(
                "TV recommendation service is not loaded."
            )

    # ------------------------------------------------------------------
    # Internal: card formatting
    # ------------------------------------------------------------------

    def _series_card(
        self,
        row_index: int,
        similarity_score: float | None = None,
    ) -> dict:
        """Build a JSON-ready dict for a single TV series."""
        row = self.catalogue.iloc[row_index]

        card: dict = {}
        for col in CARD_COLUMNS:
            value = row.get(col) if col in self.catalogue.columns else None
            card[col] = self._to_python(value)

        # Ensure int TMDB ID.
        if card.get("id") is not None:
            try:
                card["id"] = int(card["id"])
            except (TypeError, ValueError):
                pass

        # Build image URLs from paths.
        poster_path = card.pop("poster_path", None)
        backdrop_path = card.pop("backdrop_path", None)

        card["poster_url"] = (
            f"{TMDB_IMAGE_BASE_URL}{poster_path}"
            if poster_path and isinstance(poster_path, str) and poster_path.strip()
            else None
        )
        card["backdrop_url"] = (
            f"{TMDB_ORIGINAL_IMAGE_BASE_URL}{backdrop_path}"
            if backdrop_path and isinstance(backdrop_path, str) and backdrop_path.strip()
            else None
        )

        if similarity_score is not None:
            card["similarity_score"] = round(float(similarity_score), 4)
            card["match_score"] = int(
                max(0, min(99, round(float(similarity_score) * 99)))
            )

        return card

    @staticmethod
    def _to_python(value):
        """Convert numpy/pandas scalars to native Python types for JSON safety."""
        if value is None:
            return None
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            if np.isnan(value):
                return None
            return float(value)
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, float) and pd.isna(value):
            return None
        return value
