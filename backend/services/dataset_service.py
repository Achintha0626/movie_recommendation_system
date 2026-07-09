import pandas as pd

DATAFRAME_FILE = "dumped_obj/movie_dataframe_for_app.csv"
MOVIE_DATA_FILE = "dumped_obj/movie_data_for_app.csv"
PRESERVED_EXISTING_COLUMNS = {
    "weighted_avg",
    "weighted_avg_scaled",
    "popularity_scaled",
    "score_mix",
}


class DatasetService:

    def __init__(self, dataframe_file=DATAFRAME_FILE, movie_data_file=MOVIE_DATA_FILE):
        self.dataframe_file = dataframe_file
        self.movie_data_file = movie_data_file
        self.last_update_stats = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }

    def load_dataframe(self):
        return pd.read_csv(self.dataframe_file)

    def load_movie_data(self):
        return pd.read_csv(self.movie_data_file)

    def save_dataframe(self, df):
        df.to_csv(self.dataframe_file, index=False)

        movie_data_df = df.drop(columns=["index"], errors="ignore")
        movie_data_df.to_csv(self.movie_data_file, index=False)

    def get_existing_ids(self, df):
        return set(df["id"].astype(int).tolist())

    def update(self, existing_df, new_movies):
        return self.update_dataset(existing_df, new_movies)

    def update_dataset(self, existing_df, new_movies):
        self.last_update_stats = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
        }

        if not new_movies:
            return existing_df

        schema_columns = [
            column
            for column in existing_df.columns
            if column != "index"
        ]
        update_columns = [
            column
            for column in schema_columns
            if column not in PRESERVED_EXISTING_COLUMNS
        ]

        combined_df = existing_df.drop(columns=["index"], errors="ignore").copy()
        original_row_count = len(combined_df)
        combined_df = combined_df.drop_duplicates(
            subset=["id"],
            keep="first"
        ).reset_index(drop=True)
        removed_duplicates = len(combined_df) != original_row_count

        existing_ids = {
            int(movie_id): row_index
            for row_index, movie_id in combined_df["id"].items()
        }

        for movie in new_movies:
            movie_id = movie.get("id")

            if movie_id is None:
                self.last_update_stats["skipped"] += 1
                continue

            movie_id = int(movie_id)

            if movie_id not in existing_ids:
                row = {
                    column: movie.get(column)
                    for column in schema_columns
                }
                combined_df = pd.concat(
                    [combined_df, pd.DataFrame([row])],
                    ignore_index=True
                )
                existing_ids[movie_id] = combined_df.index[-1]
                self.last_update_stats["added"] += 1
                continue

            row_index = existing_ids[movie_id]
            changed = False

            for column in update_columns:
                old_value = combined_df.at[row_index, column]
                new_value = movie.get(column)

                if not self._values_equal(old_value, new_value):
                    combined_df.at[row_index, column] = new_value
                    changed = True

            if changed:
                self.last_update_stats["updated"] += 1
            else:
                self.last_update_stats["skipped"] += 1

        if (
            self.last_update_stats["added"] == 0 and
            self.last_update_stats["updated"] == 0 and
            not removed_duplicates
        ):
            return existing_df

        combined_df.insert(0, "index", range(len(combined_df)))

        self.save_dataframe(combined_df)

        return combined_df

    def _values_equal(self, old_value, new_value):
        if pd.isna(old_value) and pd.isna(new_value):
            return True

        return old_value == new_value
