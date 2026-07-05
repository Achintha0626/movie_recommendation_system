# Movie Recommendation System — Completed Work

## Project Stack

- Frontend: React 19, Vite, Axios, React Router
- Backend: FastAPI, pandas, scikit-learn, joblib
- Movie metadata: TMDB API
- User data: Browser localStorage
- Deployment targets: Vercel frontend and Render backend

## Backend Features Completed

### Recommendation API

- Loads the local movie dataset and trained similarity model.
- Preserves the original recommendation ranking logic.
- Returns up to 10 recommended movies.
- Supports optional case-insensitive genre filtering.
- Returns model-derived match percentages and recommendation explanations.
- Generates explanation reasons from shared genres, keywords, cast, directors,
  and story similarity.

### Local Movie Search

- Case-insensitive partial-title search.
- Prefix matches are prioritized.
- Returns a maximum of 10 autocomplete results.
- Returns an empty list for an empty query.

### TMDB Integration

- API key is loaded securely from `backend/.env`.
- Recommendation results include TMDB IDs, posters, release dates, ratings,
  and overviews.
- Trending movies are loaded from TMDB's daily trending endpoint.
- Movie details include backdrop, poster, runtime, genres, director, top cast,
  overview, rating, and YouTube trailer.
- Missing metadata and TMDB failures are handled safely.
- TMDB search results and movie details use in-memory caching.

### Genres

- Genres are parsed from the local dataset.
- `Science Fiction` is normalized to `Sci-Fi`.
- A useful fallback genre collection is available if dataset parsing fails.

### Deployment Readiness

- Dataset and model paths resolve relative to `backend/app.py`.
- CORS allows localhost and the production `FRONTEND_URL`.
- `PORT` is supported for hosted environments.
- A `/health` endpoint is available for Render health checks.
- Runtime dependencies are cleaned in `backend/requirements.txt`.

## Backend Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Service health check |
| GET | `/movies` | Complete local movie-title list |
| GET | `/search?query=...` | Autocomplete title search |
| GET | `/genres` | Available local genres |
| GET | `/trending` | Daily trending TMDB movies |
| GET | `/recommend/{movie_title}` | Movie recommendations |
| GET | `/recommend/{movie_title}?genre=Action` | Genre-filtered recommendations |
| GET | `/movie/{tmdb_id}` | Complete TMDB movie details |

## Frontend Features Completed

### Home and Recommendation Experience

- Modern responsive dark theme with gradient and glassmorphism styling.
- Search autocomplete with a 300 ms debounce.
- Keyboard controls using Arrow Up, Arrow Down, Enter, and Escape.
- Responsive genre filter chips.
- Loading, empty, and error states.
- Recommendation results automatically appear above Trending Today.
- Smooth scrolling to new or restored recommendations.
- Recommendation headings identify the selected movie and genre context.
- Recommendation cards display match score and explanation chips.

### Movie Cards

- TMDB poster, title, release year, rating, and overview.
- Clean `No Poster` fallback.
- Responsive card grid and hover animations.
- Cards navigate to `/movie/{id}`.
- Favorite and Watchlist controls with active states.
- Recommendation-only match scores and explanation reasons.

### Movie Details Page

- Cinematic backdrop hero.
- Poster, title, release year, rating, runtime, and genre badges.
- Overview and director information.
- Top six cast members with profile images.
- Trailer button that opens YouTube in a new tab.
- Responsive mobile layout and error/loading states.

### Trending Movies

- Daily TMDB trending section.
- Loading skeleton cards and error state.
- Trending cards link to movie details.

### Favorites and Watchlist

- Favorites stored under the `favorites` localStorage key.
- Watchlist stored under the `watchlist` localStorage key.
- Duplicate prevention by TMDB movie ID.
- Dedicated `/favorites` and `/watchlist` pages.
- Remove controls, navigation counters, and empty states.
- Data persists after refresh and synchronizes across browser tabs.

### Recently Viewed

- Opening a details page saves the movie under `recentlyViewed`.
- Movies are deduplicated by ID and ordered newest first.
- Stores a maximum of 10 movies.
- Recently viewed cards appear on Home only when data exists.

### Recommendation History

- Successful searches are stored under `recommendationHistory`.
- Stores searched movie, genre, recommendations, and timestamp.
- Duplicate movie-and-genre searches move to the top.
- Stores a maximum of 10 searches.
- History items restore the input, genre, recommendation cards, and scroll
  position.
- Individual delete and Clear All controls are available.

### Activity Dashboard

- Dashboard route: `/dashboard`.
- Summary counts for Favorites, Watchlist, Recently Viewed, and Searches.
- Top five recommended movies by match score.
- Top five most searched movies.
- Most-used genre bars, excluding `All`.
- Latest viewed movies and recommendation searches.
- Clickable drill-down cards and a first-use empty state.

## Frontend Routes

| Route | Page |
| --- | --- |
| `/` | Home, search, recommendations, trending, recent activity, history |
| `/movie/:id` | Movie details |
| `/favorites` | Favorite movies |
| `/watchlist` | Watchlist movies |
| `/dashboard` | User activity dashboard |

## Security Completed

- TMDB API key is never included in frontend code.
- `backend/.env`, `frontend/.env`, and root `.env` are ignored by Git.
- `.env.example` files were removed; use local `.env` files for private configuration.
- Frontend receives only the deployed backend URL through
  `VITE_API_BASE_URL`.

## Deployment Configuration Completed

### Render Backend

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Required environment variables: `TMDB_API_KEY`, `FRONTEND_URL`

### Vercel Frontend

- Root directory: `frontend`
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Required environment variable: `VITE_API_BASE_URL`
- SPA route rewrites are configured in `frontend/vercel.json`.

## Local Development Commands

### Backend

```powershell
cd D:\Github\movie_recommendation_system\backend
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app:app --reload
```

### Frontend

```powershell
cd D:\Github\movie_recommendation_system\frontend
npm install
npm run dev
```

### Validation

```powershell
cd D:\Github\movie_recommendation_system\frontend
npm run lint
npm run build
```

## Environment Examples

Backend `backend/.env`:

```env
TMDB_API_KEY=your_tmdb_api_key
FRONTEND_URL=http://localhost:5173
```

Frontend `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Production values and deployment steps are also documented in
`DEPLOYMENT.md`.
