"""TV series embedding generation.

Reuses the shared ``all-MiniLM-L6-v2`` model from the movie pipeline.
Saves TV-specific artifacts to ``dumped_obj/tv/`` so movie embeddings are
never touched.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
TV_DATA_DIR = BASE_DIR / "dumped_obj" / "tv"

TV_CATALOGUE_FILE = TV_DATA_DIR / "tv_catalogue.csv"
TV_EMBEDDINGS_FILE = TV_DATA_DIR / "tv_semantic_embeddings.pkl"
TV_METADATA_FILE = TV_DATA_DIR / "tv_embedding_metadata.json"
MODEL_NAME = "all-MiniLM-L6-v2"

# Fields concatenated into the text representation for embedding.
# Mirrors the movie TEXT_COLUMNS but adapted for TV-specific column names.
TV_TEXT_COLUMNS = [
    "name",
    "genres",
    "keywords",
    "tagline",
    "overview",
]


class TVEmbeddingService:
    """Build and persist semantic embeddings for the TV catalogue."""

    def __init__(
        self,
        data_file: Path | str = TV_CATALOGUE_FILE,
        embeddings_file: Path | str = TV_EMBEDDINGS_FILE,
        metadata_file: Path | str = TV_METADATA_FILE,
        model_name: str = MODEL_NAME,
    ):
        self.data_file = Path(data_file)
        self.embeddings_file = Path(embeddings_file)
        self.metadata_file = Path(metadata_file)
        self.model_name = model_name
        self.model = None
        self.embeddings = None
        self.embedding_metadata: dict = {}

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required to build TV embeddings. "
                    "Install it before running TVEmbeddingService.rebuild()."
                ) from e

            self.model = SentenceTransformer(self.model_name)

        return self.model

    # ------------------------------------------------------------------
    # Dataframe helpers
    # ------------------------------------------------------------------

    def load_dataframe(self) -> pd.DataFrame:
        return pd.read_csv(self.data_file)

    # ------------------------------------------------------------------
    # Embedding build
    # ------------------------------------------------------------------

    def build_embeddings(self, df: pd.DataFrame):
        model = self.load_model()
        texts = self._build_embedding_texts(df)

        self.embeddings = model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        return self.embeddings

    def save_embeddings(self, path: Path | str | None = None) -> None:
        if self.embeddings is None:
            raise ValueError("No TV embeddings have been built yet.")

        output_path = Path(path or self.embeddings_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.embeddings, output_path)

    def load_embeddings(self, path: Path | str | None = None):
        input_path = Path(path or self.embeddings_file)
        self.embeddings = joblib.load(input_path)
        return self.embeddings

    # ------------------------------------------------------------------
    # Full rebuild
    # ------------------------------------------------------------------

    def rebuild(self) -> None:
        """Load the TV catalogue, build embeddings, and persist everything."""
        start_time = time.perf_counter()

        df = self.load_dataframe()

        if df.empty:
            print("TV catalogue is empty — nothing to embed.")
            return

        embeddings = self.build_embeddings(df)
        self.save_embeddings()
        self._save_metadata(df, embeddings)

        time_taken = time.perf_counter() - start_time

        print("TV series processed:", len(df))
        print("Embedding dimension:", self._embedding_dimension(embeddings))
        print("Time taken:", f"{time_taken:.2f} seconds")

    # ------------------------------------------------------------------
    # Text representation
    # ------------------------------------------------------------------

    def _build_embedding_texts(self, df: pd.DataFrame) -> list[str]:
        text_df = df.copy()

        for column in TV_TEXT_COLUMNS:
            if column not in text_df.columns:
                text_df[column] = ""

            text_df[column] = text_df[column].fillna("").astype(str)

        return text_df[TV_TEXT_COLUMNS].apply(
            lambda row: " ".join(
                value.strip()
                for value in row
                if value.strip()
            ),
            axis=1,
        ).tolist()

    # ------------------------------------------------------------------
    # Metadata persistence
    # ------------------------------------------------------------------

    def _save_metadata(self, df: pd.DataFrame, embeddings) -> None:
        self.embedding_metadata = {
            "model": self.model_name,
            "embedding_dimension": self._embedding_dimension(embeddings),
            "series_count": len(df),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with self.metadata_file.open("w", encoding="utf-8") as f:
            json.dump(self.embedding_metadata, f, indent=2)

    def _embedding_dimension(self, embeddings) -> int:
        if embeddings is not None and len(embeddings.shape) == 2:
            return int(embeddings.shape[1])

        model = self.load_model()
        return int(model.get_sentence_embedding_dimension())


if __name__ == "__main__":
    service = TVEmbeddingService()
    service.rebuild()
