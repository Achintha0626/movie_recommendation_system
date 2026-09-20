# 🎬 CineMatch – Hybrid AI Movie Recommendation System

CineMatch is a full-stack movie discovery and recommendation application powered by **Machine Learning, Semantic AI, and TMDB metadata**.

Users can search for movies they like and receive intelligently ranked recommendations based on semantic meaning, movie metadata, genres, keywords, franchise relationships, popularity, and ratings.

The application also provides trending movies, detailed movie information, favorites, watchlists, recently viewed movies, recommendation history, and a personal activity dashboard.

The movie catalogue and ML recommendation artifacts are automatically maintained using **GitHub Actions** and TMDB.

---

# 🌐 Live Demo

## Frontend

https://movie-recommendation-system-nu-pearl.vercel.app

## Backend

Hosted on **Render**.

---

# ✨ Features

## 🎯 Hybrid AI Movie Recommendations

CineMatch uses a **hybrid recommendation engine** instead of relying on a single similarity technique.

Features include:

- Semantic movie similarity
- Metadata-based similarity
- Genre similarity
- Keyword similarity
- Franchise / collection relationships
- Popularity signals
- Movie rating signals
- Top 10 ranked recommendations
- Match percentage for each recommendation
- Human-readable recommendation explanations
- Genre filtering
- Original recommendation ranking preservation

Example recommendation reasons include:

- Same franchise / similar title
- Similar story
- Similar genre
- Similar keywords
- Shared cast
- Same director
- Popular / highly rated movie

---

# 🧠 Recommendation Engine

CineMatch combines traditional Machine Learning with semantic NLP embeddings.

The recommendation pipeline uses two major similarity approaches.

## 1. Metadata Similarity

Movie metadata includes information such as:

- Overview
- Genres
- Keywords
- Cast
- Crew / Director

Metadata is processed using **TF-IDF** and a **Sigmoid Kernel similarity matrix**.

The generated similarity matrix is stored as:

```text
backend/dumped_obj/sigmoid_kernel.pkl
```

Precomputing this matrix allows the backend to generate recommendations without recalculating metadata similarity for every request.

---

## 2. Semantic Similarity

CineMatch also understands the **meaning and context** of movie information instead of comparing only matching words.

Semantic embeddings are generated using the Sentence Transformer model:

```text
all-MiniLM-L6-v2
```

Each movie is represented as a **384-dimensional embedding vector**.

Semantic similarity between movies is calculated using **Cosine Similarity**.

Generated embeddings are stored in:

```text
backend/dumped_obj/semantic_embeddings.pkl
```

Embedding information is stored in:

```text
backend/dumped_obj/embedding_metadata.json
```

---

# ⚖️ Hybrid Ranking

The recommendation engine combines multiple signals to produce the final ranking.

The main ranking signals include:

| Signal | Purpose |
|---|---|
| Semantic similarity | Understands similarity in movie meaning/story |
| Metadata similarity | Compares movie metadata |
| Collection / franchise | Identifies related movie series |
| Keywords | Detects shared themes/topics |
| Popularity | Adds popularity information |
| Vote average | Adds rating information |

This hybrid approach provides more meaningful recommendations than relying on a single similarity method.

---

# 💡 Recommendation Explanations

CineMatch does not only return a movie recommendation.

It also explains **why the movie was recommended**.

Examples:

```text
Similar story overview
Similar genre
Shared cast
Same director
Same franchise / similar title
Popular/high-rated movie
```

This makes the recommendation system more understandable to users.

---

# 🔍 Movie Search

The application provides fast movie search with:

- Autocomplete
- Case-insensitive search
- Prefix prioritization
- Partial title matching
- Up to 10 search suggestions

---

# 🎞 Movie Details

Users can open a movie and view:

- High-resolution backdrop
- Movie poster
- Overview
- Release date
- Runtime
- Genres
- Director
- Top cast
- TMDB rating
- YouTube trailer

Detailed movie metadata is retrieved from the **TMDB API**.

---

# 🔥 Trending Movies

The Home page displays daily trending movies using live data from TMDB.

---

# ❤️ Favorites

Users can:

- Add movies to favorites
- Remove movies from favorites
- Access saved favorites later

Favorites are stored using browser **LocalStorage**.

---

# 📌 Watchlist

Users can:

- Add movies to their watchlist
- Remove movies
- Prevent duplicate entries
- Access the watchlist after refreshing the browser

Watchlist information is stored in LocalStorage.

---

# 🕒 Recently Viewed

CineMatch automatically tracks recently viewed movies.

Features include:

- Latest viewed movies
- Maximum recent-history management
- Quick access from the Home page

---

# 📜 Recommendation History

Previous recommendation searches are stored locally.

Users can:

- View previous searches
- Restore previous recommendations
- Delete individual history entries
- Clear recommendation history

---

# 📊 Dashboard

The dashboard summarizes user activity.

It includes:

- Favorite count
- Watchlist count
- Recently viewed movies
- Recommendation/search history
- Most searched movies
- Top recommendation scores
- Genre usage statistics

---

# 🔄 Automatic Movie Catalogue Updates

CineMatch includes an automated movie catalogue maintenance pipeline using **GitHub Actions**.

The workflow runs automatically every week.

Current schedule:

```yaml
cron: "17 2 * * 0"
```

This runs every **Sunday at 02:17 UTC**.

The workflow can also be triggered manually from GitHub Actions.

## Automatic Update Pipeline

```text
GitHub Actions starts
        ↓
Check TMDB for changed/new movie data
        ↓
Incrementally update movie catalogue
        ↓
Check whether catalogue changed
        ↓
If catalogue changed
        ↓
Rebuild metadata similarity matrix
        ↓
Rebuild semantic embeddings
        ↓
Validate generated ML artifacts
        ↓
Commit generated files
        ↓
Push automatically to main
        ↓
Render detects the new commit
        ↓
Backend automatically redeploys
```

This means the recommendation catalogue can remain up to date without manually rebuilding the ML files every week.

---

# 🛡️ ML Artifact Validation

Before updated recommendation files are committed, the GitHub Actions workflow validates them.

The workflow verifies:

- Movie dataframe exists
- Application movie CSV exists
- Similarity matrix exists
- Semantic embeddings exist
- Embedding metadata exists
- Dataset row counts match
- Similarity matrix dimensions match the dataset
- Number of embeddings matches the number of movies
- Embedding metadata movie count matches the dataset

For example:

```text
Movie rows: 1412
Similarity shape: (1412, 1412)
Embedding shape: (1412, 384)
```

If these values do not align correctly, the workflow stops instead of committing inconsistent recommendation artifacts.

This prevents dataset/artifact synchronization problems.

---

# ⚡ Optimized GitHub Actions ML Environment

The GitHub Actions workflow uses **CPU-only PyTorch** when rebuilding semantic embeddings.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

This prevents unnecessary NVIDIA/CUDA packages from being downloaded on the GitHub Actions CPU runner and significantly reduces dependency installation time.

---

# 🚀 Automatic Backend Deployment

The backend is hosted on **Render**.

Render is connected to the GitHub repository with:

```text
Auto-Deploy: On Commit
```

Therefore, when the weekly GitHub Actions workflow finds movie catalogue changes:

```text
TMDB update
   ↓
GitHub Action rebuilds ML artifacts
   ↓
GitHub Action pushes to main
   ↓
Render detects new commit
   ↓
Render automatically redeploys backend
   ↓
Updated recommendation data becomes available
```

If no catalogue changes are detected, no generated catalogue commit is required.

---

# 🏗️ System Architecture

```text
                         ┌───────────────────┐
                         │       User        │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   React Frontend  │
                         │      Vercel       │
                         └─────────┬─────────┘
                                   │
                                 Axios
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  FastAPI Backend  │
                         │      Render       │
                         └─────────┬─────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
                ▼                  ▼                  ▼
        Metadata Similarity   Semantic AI          TMDB API
                │                  │
          TF-IDF + Kernel     MiniLM Embeddings
                │                  │
                └─────────┬────────┘
                          │
                          ▼
                 Hybrid Ranking Engine
                          │
                          ▼
                Top 10 Recommendations
                          │
                          ▼
              Recommendation Explanation
```

---

# 🛠️ Tech Stack

## Frontend

- React 19
- Vite
- React Router
- Axios
- CSS
- LocalStorage

## Backend

- FastAPI
- Python
- Pandas
- NumPy
- Scikit-learn
- SciPy
- Joblib
- Requests

## AI / Machine Learning

- Sentence Transformers
- `all-MiniLM-L6-v2`
- Semantic Embeddings
- Cosine Similarity
- TF-IDF
- Sigmoid Kernel
- Hybrid Recommendation Ranking

## External API

- TMDB API

## DevOps / Automation

- GitHub Actions
- Automated weekly catalogue synchronization
- Automated ML artifact rebuilding
- Automated artifact validation
- Automated Git commits
- Render Auto-Deploy

## Deployment

- **Frontend:** Vercel
- **Backend:** Render

---

# 📁 Project Structure

```text
movie_recommendation_system/
│
├── .github/
│   └── workflows/
│       └── update-movie-catalogue.yml
│
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── rebuild_similarity.py
│   │
│   ├── scripts/
│   │   └── incremental_update.py
│   │
│   ├── services/
│   │   ├── dataset_service.py
│   │   ├── embedding_service.py
│   │   ├── explanation_service.py
│   │   ├── hybrid_ranking_service.py
│   │   ├── semantic_similarity_service.py
│   │   ├── similarity_service.py
│   │   └── tmdb_service.py
│   │
│   └── dumped_obj/
│       ├── movie_dataframe_for_app.csv
│       ├── movie_data_for_app.csv
│       ├── sigmoid_kernel.pkl
│       ├── semantic_embeddings.pkl
│       └── embedding_metadata.json
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── DEPLOYMENT.md
└── README.md
```

---

# 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Backend health check |
| GET | `/movies` | Get movie titles |
| GET | `/search?query=` | Search movies |
| GET | `/genres` | Get available genres |
| GET | `/trending` | Get daily trending movies |
| GET | `/recommend/{movie}` | Generate movie recommendations |
| GET | `/movie/{tmdb_id}` | Get detailed movie information |

---

# 🚀 Installation

## 1. Clone Repository

```bash
git clone https://github.com/Achintha0626/movie_recommendation_system.git

cd movie_recommendation_system
```

---

## 2. Backend Setup

```bash
cd backend

python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FastAPI:

```bash
uvicorn app:app --reload
```

Backend runs at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

---

## 3. Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

Frontend runs at:

```text
http://localhost:5173
```

---

# ⚙️ Environment Variables

## Backend

Create:

```text
backend/.env
```

Add:

```env
TMDB_API_KEY=your_tmdb_api_key
FRONTEND_URL=http://localhost:5173
```

---

## Frontend

Create:

```text
frontend/.env
```

Add:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

# 🔐 GitHub Actions Secret

The automatic movie catalogue workflow requires a TMDB API key.

Add the following GitHub Actions repository secret:

```text
TMDB_API_KEY
```

The workflow verifies that this secret exists before attempting to synchronize the movie catalogue.

Never commit the real TMDB API key directly to the repository.

---

# ☁️ Deployment

## Frontend – Vercel

The React/Vite frontend is deployed using **Vercel**.

Production:

https://movie-recommendation-system-nu-pearl.vercel.app

## Backend – Render

The FastAPI backend is hosted using **Render**.

Render automatically redeploys when relevant changes are pushed to the configured production branch.

---

# 💾 Client-Side Storage

CineMatch currently does not require user accounts or a database for personal movie activity.

The following information is stored in browser LocalStorage:

```text
favorites
watchlist
recentlyViewed
recommendationHistory
```

This keeps the application lightweight while still providing personalized user features.

---

# 🔄 Complete Production Flow

```text
User opens CineMatch
        ↓
React frontend (Vercel)
        ↓
FastAPI backend (Render)
        ↓
User searches for a movie
        ↓
Hybrid Recommendation Engine
        ↓
Metadata Similarity + Semantic Similarity
        ↓
Additional ranking signals
        ↓
Top 10 recommendations
        ↓
TMDB metadata enrichment
        ↓
Recommendation explanations
        ↓
Results displayed to user
```

The movie catalogue is maintained separately:

```text
TMDB
  ↓
Weekly GitHub Actions workflow
  ↓
Update catalogue
  ↓
Rebuild ML artifacts
  ↓
Validate artifacts
  ↓
Commit + Push
  ↓
Render Auto-Deploy
  ↓
Updated production backend
```

---

# 👨‍💻 Author

**Achintha**

GitHub:

https://github.com/Achintha0626

---

# ⭐ Support

If you find CineMatch useful or interesting, consider giving the project a ⭐ on GitHub.