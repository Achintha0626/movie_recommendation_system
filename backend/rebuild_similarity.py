import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import sigmoid_kernel

DATA_FILE = "dumped_obj/movie_dataframe_updated_TEST.csv"
OUTPUT_FILE = "dumped_obj/sigmoid_kernel_TEST.pkl"

df = pd.read_csv(DATA_FILE)

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

tfidf = TfidfVectorizer(stop_words="english")
tfidf_matrix = tfidf.fit_transform(df["combined_features"])

sig = sigmoid_kernel(tfidf_matrix, tfidf_matrix)

joblib.dump(sig, OUTPUT_FILE)

print("Dataset size:", df.shape)
print("Similarity matrix shape:", sig.shape)
print("Saved:", OUTPUT_FILE)