import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import sigmoid_kernel

DATA_FILE = "dumped_obj/movie_dataframe_for_app.csv"
OUTPUT_FILE = "dumped_obj/sigmoid_kernel.pkl"


class SimilarityService:

    def __init__(self, data_file=DATA_FILE, output_file=OUTPUT_FILE):
        self.data_file = data_file
        self.output_file = output_file

    def load_dataframe(self):
        return pd.read_csv(self.data_file)

    def build_combined_features(self, df):
        df["overview"] = df["overview"].fillna("")
        df["genres"] = df["genres"].fillna("")
        df["keywords"] = df["keywords"].fillna("")
        df["cast"] = df["cast"].fillna("")
        df["crew"] = df["crew"].fillna("")

        df["combined_features"] = (
            df["overview"] + " " +
            df["genres"] + " " +
            df["keywords"] + " " +
            df["cast"] + " " +
            df["crew"]
        )

        return df

    def vectorize(self, df):
        tfidf = TfidfVectorizer(stop_words="english")
        return tfidf.fit_transform(df["combined_features"])

    def generate_similarity_matrix(self, tfidf_matrix):
        return sigmoid_kernel(tfidf_matrix, tfidf_matrix)

    def save_similarity_matrix(self, similarity_matrix):
        joblib.dump(similarity_matrix, self.output_file)

    def rebuild(self, verbose=True):
        df = self.load_dataframe()
        df = self.build_combined_features(df)
        tfidf_matrix = self.vectorize(df)
        similarity_matrix = self.generate_similarity_matrix(tfidf_matrix)
        self.save_similarity_matrix(similarity_matrix)

        if verbose:
            print("Dataset size:", df.shape)
            print("Similarity matrix shape:", similarity_matrix.shape)
            print("Saved:", self.output_file)

        return similarity_matrix
