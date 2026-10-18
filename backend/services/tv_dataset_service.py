"""TV series catalogue storage.

Follows the same pattern as ``DatasetService`` but writes to a separate
``dumped_obj/tv/`` directory so TV data never overwrites movie artifacts.
"""

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
TV_DATA_DIR = BASE_DIR / "dumped_obj" / "tv"

TV_CATALOGUE_FILE = TV_DATA_DIR / "tv_catalogue.csv"

# Columns that are computed locally and must not be overwritten by TMDB
# refreshes (same concept as the movie PRESERVED_EXISTING_COLUMNS).
PRESERVED_COLUMNS: set[str] = set()

# The canonical column order for the TV catalogue.
TV_SCHEMA_COLUMNS = [
    "id",
    "name",
    "original_name",
    "overview",
    "first_air_date",
    "genres",
    "original_language",
    "popularity",
    "vote_average",
    "vote_count",
    "poster_path",
    "backdrop_path",
    "number_of_seasons",
    "number_of_episodes",
    "status",
    "keywords",
    "cast",
    "created_by",
    "production_companies",
    "networks",
    "spoken_languages",
    "tagline",
]


class TVDatasetService:
    """Manage the on-disk TV series catalogue CSV."""

    def __init__(self, catalogue_file: Path | str = TV_CATALOGUE_FILE):
        self.catalogue_file = Path(catalogue_file)
        self.last_update_stats = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def load_catalogue(self) -> pd.DataFrame:
        if not self.catalogue_file.exists():
            return pd.DataFrame(columns=TV_SCHEMA_COLUMNS)

        return pd.read_csv(self.catalogue_file)

    def save_catalogue(self, df: pd.DataFrame) -> None:
        self.catalogue_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.catalogue_file, index=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_existing_ids(self, df: pd.DataFrame) -> set[int]:
        if df.empty or "id" not in df.columns:
            return set()

        return set(df["id"].dropna().astype(int).tolist())

    # ------------------------------------------------------------------
    # Update (upsert)
    # ------------------------------------------------------------------

    def update(self, existing_df: pd.DataFrame, new_series: list[dict]) -> pd.DataFrame:
        """Merge new TV series records into the existing catalogue.

        Mirrors ``DatasetService.update_dataset`` — adds new rows and
        updates changed rows, but never removes. Optimized for batch
        insertions of thousands of records.
        """
        self.last_update_stats = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }

        if not new_series:
            return existing_df

        # Determine which columns to actually use
        if existing_df.empty:
            schema_columns = list(TV_SCHEMA_COLUMNS)
            combined_df = pd.DataFrame(columns=schema_columns)
        else:
            schema_columns = [
                col for col in existing_df.columns
                if col != "index"
            ]
            combined_df = existing_df.copy()
            if "index" in combined_df.columns:
                combined_df = combined_df.drop(columns=["index"])

        update_columns = [
            col for col in schema_columns
            if col not in PRESERVED_COLUMNS
        ]

        # Deduplicate existing rows by TMDB ID
        if not combined_df.empty:
            combined_df = combined_df.drop_duplicates(
                subset=["id"], keep="first"
            ).reset_index(drop=True)

        existing_ids: dict[int, int] = {}
        if not combined_df.empty:
            existing_ids = {
                int(series_id): row_idx
                for row_idx, series_id in combined_df["id"].items()
                if pd.notna(series_id)
            }

        new_rows: list[dict] = []
        seen_new_ids: set[int] = set()

        for series in new_series:
            raw_id = series.get("id")
            if raw_id is None:
                self.last_update_stats["skipped"] += 1
                continue

            try:
                series_id = int(raw_id)
            except (ValueError, TypeError):
                self.last_update_stats["skipped"] += 1
                continue

            if series_id not in existing_ids:
                if series_id in seen_new_ids:
                    self.last_update_stats["skipped"] += 1
                    continue
                seen_new_ids.add(series_id)

                row = {
                    col: series.get(col)
                    for col in schema_columns
                }
                new_rows.append(row)
                continue

            row_idx = existing_ids[series_id]
            changed = False

            for col in update_columns:
                old_value = combined_df.at[row_idx, col]
                new_value = series.get(col)

                if not self._values_equal(old_value, new_value):
                    combined_df.at[row_idx, col] = new_value
                    changed = True

            if changed:
                self.last_update_stats["updated"] += 1
            else:
                self.last_update_stats["skipped"] += 1

        if new_rows:
            new_df = pd.DataFrame(new_rows, columns=schema_columns)
            if combined_df.empty:
                combined_df = new_df
            else:
                combined_df = pd.concat([combined_df, new_df], ignore_index=True)
            self.last_update_stats["added"] = len(new_rows)

        if (
            self.last_update_stats["added"] == 0
            and self.last_update_stats["updated"] == 0
        ):
            return existing_df

        # Final deduplication safeguard
        combined_df = combined_df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)

        self.save_catalogue(combined_df)
        return combined_df

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _values_equal(old_value, new_value) -> bool:
        if pd.isna(old_value) and (new_value is None or (isinstance(new_value, float) and pd.isna(new_value))):
            return True

        return old_value == new_value
