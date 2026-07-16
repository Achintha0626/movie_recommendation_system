import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "dumped_obj" / "movie_dataframe_for_app.csv"
EMBEDDINGS_FILE = BASE_DIR / "dumped_obj" / "semantic_embeddings.pkl"
METADATA_FILE = BASE_DIR / "dumped_obj" / "embedding_metadata.json"
MODEL_NAME = "all-MiniLM-L6-v2"
TEXT_COLUMNS = [
    "collection",
    "original_title",
    "genres",
    "keywords",
    "tagline",
    "overview",
]


class EmbeddingService:

    def __init__(
        self,
        data_file=DATA_FILE,
        embeddings_file=EMBEDDINGS_FILE,
        metadata_file=METADATA_FILE,
        model_name=MODEL_NAME,
    ):
        self.data_file = Path(data_file)
        self.embeddings_file = Path(embeddings_file)
        self.metadata_file = Path(metadata_file)
        self.model_name = model_name
        self.model = None
        self.embeddings = None
        self.embedding_metadata = {}

    def load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required to build embeddings. "
                    "Install it before running EmbeddingService.rebuild()."
                ) from e

            self.model = SentenceTransformer(self.model_name)

        return self.model

    def load_dataframe(self):
        return pd.read_csv(self.data_file)

    def build_embeddings(self, df):
        model = self.load_model()
        texts = self._build_embedding_texts(df)

        self.embeddings = model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        return self.embeddings

    def save_embeddings(self, path=None):
        if self.embeddings is None:
            raise ValueError("No embeddings have been built yet.")

        output_path = Path(path or self.embeddings_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.embeddings, output_path)

    def load_embeddings(self, path=None):
        input_path = Path(path or self.embeddings_file)
        self.embeddings = joblib.load(input_path)
        return self.embeddings

    def rebuild(self):
        start_time = time.perf_counter()

        df = self.load_dataframe()
        embeddings = self.build_embeddings(df)
        self.save_embeddings(self.embeddings_file)
        self._save_metadata(df, embeddings)

        time_taken = time.perf_counter() - start_time

        print("Movies processed:", len(df))
        print("Embedding dimension:", self._embedding_dimension(embeddings))
        print("Time taken:", f"{time_taken:.2f} seconds")

        return embeddings

    def _build_embedding_texts(self, df):
        text_df = df.copy()

        for column in TEXT_COLUMNS:
            if column not in text_df.columns:
                text_df[column] = ""

            text_df[column] = text_df[column].fillna("").astype(str)

        return text_df[TEXT_COLUMNS].apply(
            lambda row: " ".join(
                value.strip()
                for value in row
                if value.strip()
            ),
            axis=1,
        ).tolist()

    def _save_metadata(self, df, embeddings):
        self.embedding_metadata = {
            "model": self.model_name,
            "embedding_dimension": self._embedding_dimension(embeddings),
            "movie_count": len(df),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with self.metadata_file.open("w", encoding="utf-8") as metadata_file:
            json.dump(self.embedding_metadata, metadata_file, indent=2)

    def _embedding_dimension(self, embeddings):
        if embeddings is not None and len(embeddings.shape) == 2:
            return int(embeddings.shape[1])

        model = self.load_model()
        return int(model.get_sentence_embedding_dimension())


if __name__ == "__main__":
    service = EmbeddingService()
    service.rebuild()
