from pathlib import Path

import joblib
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]
EMBEDDINGS_FILE = BASE_DIR / "dumped_obj" / "semantic_embeddings.pkl"


class SemanticSimilarityError(RuntimeError):
    pass


class SemanticSimilarityService:

    def __init__(self, dataframe, embeddings_path=EMBEDDINGS_FILE):
        self.dataframe = dataframe
        self.embeddings_path = Path(embeddings_path)
        self.embeddings = self.load_embeddings(self.embeddings_path)
        self.validate()

    def load_embeddings(self, path=None):
        embeddings_path = Path(path or self.embeddings_path)

        if not embeddings_path.exists():
            raise SemanticSimilarityError(
                f"Semantic embeddings file not found: {embeddings_path}"
            )

        try:
            embeddings = joblib.load(embeddings_path)
        except Exception as e:
            raise SemanticSimilarityError(
                f"Could not load semantic embeddings: {embeddings_path}"
            ) from e

        return np.asarray(embeddings, dtype=float)

    def validate(self):
        if self.embeddings.ndim != 2:
            raise SemanticSimilarityError(
                "Semantic embeddings must be a 2D matrix."
            )

        movie_count = len(self.dataframe)
        embedding_count = self.embeddings.shape[0]

        if embedding_count != movie_count:
            raise SemanticSimilarityError(
                "Semantic embedding row count does not match dataframe row "
                f"count: embeddings={embedding_count}, dataframe={movie_count}"
            )

        if self.embeddings.shape[1] <= 0:
            raise SemanticSimilarityError(
                "Semantic embeddings must have at least one dimension."
            )

    def similarity_scores(self, selected_index):
        self._validate_index(selected_index)

        selected_embedding = self.embeddings[selected_index]
        selected_norm = np.linalg.norm(selected_embedding)
        all_norms = np.linalg.norm(self.embeddings, axis=1)
        denominator = selected_norm * all_norms

        with np.errstate(divide="ignore", invalid="ignore"):
            scores = np.divide(
                self.embeddings @ selected_embedding,
                denominator,
                out=np.zeros(len(self.embeddings), dtype=float),
                where=denominator != 0,
            )

        scores[selected_index] = -1.0

        return {
            row_index: float(score)
            for row_index, score in enumerate(scores)
            if row_index != selected_index and np.isfinite(score)
        }

    def top_scores(self, selected_index, limit=100):
        scores = self.similarity_scores(selected_index)
        return sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]

    @property
    def embedding_dimension(self):
        return int(self.embeddings.shape[1])

    def _validate_index(self, selected_index):
        if selected_index < 0 or selected_index >= len(self.dataframe):
            raise SemanticSimilarityError(
                f"Selected movie index out of range: {selected_index}"
            )
