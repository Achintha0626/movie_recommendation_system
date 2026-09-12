# CineMatch Project Status Audit

**Audit date:** 2026-09-10  
**Scope:** Read-only audit of the repository as it existed during this investigation.  
**Change policy:** This report is the only new file created. Existing source files and generated artifacts were not modified.

## 1. Project Overview

CineMatch is a movie-discovery application. A user searches for a movie they already like, receives ranked recommendations, filters them by genre, opens TMDB-backed movie details, and saves movies locally as favorites or watchlist entries. The application also keeps recently viewed movies and recommendation searches in the browser.

The project uses:

- React 19, React Router, Axios, and Vite in `frontend/`.
- FastAPI, Pandas, NumPy, scikit-learn, Joblib, and Sentence Transformers in `backend/`.
- A local CSV movie catalogue and precomputed ML artifacts.
- TMDB for search-result metadata, trending movies, and detailed movie pages.
- Browser `localStorage` for user activity. There is no database or authentication system.

Actual high-level flow:

```text
User
  |
  v
React/Vite frontend
  |  Axios HTTP requests
  v
FastAPI app.py
  |-- local catalogue search and genres
  |-- hybrid recommendation services and generated artifacts
  |-- TMDB HTTP requests for enrichment/details/trending
  v
JSON response
  |
  v
React state, localStorage, and UI
```

## 2. Current Project Status

| Feature | Status | Evidence/File | Explanation |
|---|---|---|---|
| Movie search | ✅ Complete | `frontend/src/App.jsx`, `backend/app.py` `/search` | Search is debounced by effect timing through state changes, prefix matches are prioritized, and up to ten titles are returned. |
| Autocomplete | ✅ Complete | `frontend/src/App.jsx` | Dropdown, keyboard navigation, escape handling, loading and empty states are implemented. |
| Movie details | ✅ Complete with external dependency | `frontend/src/MovieDetails.jsx`, `backend/app.py` `/movie/{tmdb_id}` | Details, cast, director, trailer, poster, and backdrop are normalized from TMDB. It depends on a valid TMDB key and network. |
| Trending movies | ✅ Complete with external dependency | `frontend/src/App.jsx`, `backend/app.py` `/trending` | Loads up to twelve TMDB trending movies and supports load-more display. |
| Recommendations | ✅ Complete | `backend/app.py`, `backend/services/hybrid_ranking_service.py` | Hybrid ranking returns ten recommendations for a catalogue title. |
| Similarity scoring | ✅ Complete | `backend/services/similarity_service.py`, `semantic_similarity_service.py` | Metadata and semantic artifacts are loaded and dimension-validated. |
| Recommendation explanations | ✅ Complete | `backend/services/explanation_service.py` | Explanations are generated from genres, keywords, overview terms, cast, directors, collections, and score signals. |
| Genre filtering | ✅ Complete | `backend/app.py`, `HybridRankingService._has_genre` | `/genres` exposes catalogue genres and `/recommend` validates and applies a canonical filter. |
| Favorites | ✅ Complete | `frontend/src/useMovieCollections.js`, `App.jsx` | Browser-local collection with duplicate prevention, toggling, removal, and navigation. |
| Watchlist | ✅ Complete | `frontend/src/useMovieCollections.js`, `App.jsx` | Same local persistence and controls as favorites. |
| Recently viewed | ✅ Complete | `frontend/src/useMovieActivity.js`, `MovieDetails.jsx` | Successful detail loads add normalized movies, deduplicate by ID, and retain ten. |
| Recommendation history | ✅ Complete | `frontend/src/useMovieActivity.js`, `App.jsx` | Successful searches are retained, restored, deleted individually, or cleared; maximum ten unique movie/genre searches. |
| Dashboard | ✅ Complete | `frontend/src/Dashboard.jsx` | Computes summary counts, top recommendations, most searched movies, genre usage, and latest activity from local state. |
| TMDB integration | ✅ Complete with external dependency | `backend/app.py`, `backend/services/tmdb_service.py` | Production request helpers and catalogue-update helpers exist. Runtime app uses direct requests in `app.py`. |
| Error handling | 🟡 Partially complete | `app.py`, React components | Main request failures have user-visible fallbacks, but there is no global frontend error boundary and some startup/configuration errors fail during import. |
| Responsive UI | ⚠️ Needs verification | `frontend/src/*.css` | Responsive CSS exists, but no automated browser/device verification was found in the repository. |
| Backend API | ✅ Complete | `backend/app.py` | Seven application endpoints plus FastAPI documentation endpoints are registered. |
| Frontend API integration | ✅ Complete | `frontend/src/config.js`, `App.jsx`, `MovieDetails.jsx` | Axios calls match the application routes. Production URL is hardcoded as a fallback. |
| Deployment | 🟡 Partially complete | `frontend/vercel.json`, `.github/workflows/update-movie-catalogue.yml` | Frontend Vercel routing and backend catalogue automation exist; no backend platform manifest or reproducible backend deployment file is tracked. |

The regenerated artifacts were verified during this audit: dataframe 1,368 rows, semantic embeddings `(1368, 384)`, and metadata similarity `(1368, 1368)`.

## 3. Complete User Flows

### A. Opening the application

`frontend/src/main.jsx` mounts `App` inside `StrictMode` and `BrowserRouter`. `App` initializes `useMovieActivity` and `useMovieCollections`, then renders the route selected by React Router. The home route renders `Home` in `frontend/src/App.jsx`.

`Home` immediately requests `/trending` and `/genres` with Axios. The backend returns TMDB trending cards and catalogue-derived genres. Skeletons, success content, and error states are rendered from local React state. Local collections and activity are read synchronously from `localStorage` by the hooks.

### B. Searching for a movie

`Home.handleSearchChange` updates the input and opens the suggestion dropdown. An effect requests `GET /search?query=...`. `app.search_movies` normalizes the query, scans the in-memory `movie_titles` list, prioritizes prefixes, and returns up to ten titles. The response becomes `searchResponse.results`, which renders keyboard-accessible suggestion buttons.

### C. Opening movie details

A movie card links to `/movie/{id}`. `MovieDetails` reads the route ID, requests `GET /movie/{tmdb_id}`, and calls `get_tmdb_movie_details` in `app.py`. That function requests TMDB movie details with `append_to_response=credits,videos`, extracts the director, first six cast members, images, genres, and the first YouTube trailer, then returns normalized JSON. The frontend records the successful movie in `useMovieActivity` and renders the detail page.

### D. Requesting recommendations

`Home.getRecommendations` requests `GET /recommend/{encoded_title}?genre=...`. `app.recommend` resolves the exact title through `indices`, validates the requested genre, calls `HybridRankingService.recommend`, enriches the ten returned catalogue titles concurrently with `search_tmdb_movie`, and generates explanations with `ExplanationService.explain`. The response is stored in React state, added to recommendation history, and rendered as movie cards with match scores and reasons.

### E. Adding a favorite

A `MovieCard` invokes `collections.toggleFavorite(movie)`. `useMovieCollections` normalizes the card to a small local object, identifies it by stringified TMDB ID, toggles it in React state, and persists the full collection to `localStorage` under `favorites`. The favorites route renders the saved cards.

### F. Adding to the watchlist

The flow is identical to favorites, using `toggleWatchlist`, the `watchlist` state, and the `watchlist` storage key. The `/watchlist` route renders the collection.

### G. Viewing recently viewed movies

`MovieDetails` calls `onMovieViewed` only after a successful details response. `addRecentlyViewed` stores a normalized movie, moves it to the front, removes the same ID elsewhere, and caps the list at ten. `Home` and `Dashboard` render the list as links back to detail pages.

### H. Viewing recommendation history

`Home` calls `activity.addRecommendationHistory` only when recommendations are returned. The hook stores the selected title, genre, normalized recommendation card data, and timestamp. History cards can restore the recommendation list without another API request, delete one entry, or clear all history.

### I. Opening the dashboard

The `/dashboard` route renders `Dashboard` with shared activity and collection state. It derives counts and analytics in the browser: top recommendation scores, most searched movies, genre counts, recent views, and recent searches. No backend dashboard endpoint exists.

### J. Viewing trending movies

`Home` requests `/trending` on mount. `app.trending_movies` calls TMDB's trending endpoint, normalizes the first twelve results, and returns them. The frontend displays six initially and reveals more locally. A missing key or TMDB failure produces a visible error state.

## 4. Recommendation Engine

### Simple explanation

The system uses two kinds of similarity:

1. **Metadata similarity:** movies are represented by words from their overview, genres, keywords, cast, and crew. TF-IDF gives more weight to words that distinguish one movie from the rest. A sigmoid kernel compares every pair and stores the result in a matrix.
2. **Semantic similarity:** `all-MiniLM-L6-v2` converts a combined movie description into a 384-number vector. Movies with vectors pointing in a similar direction have a high cosine similarity, even when they do not share the exact words.

The hybrid ranker combines these signals with collection/franchise, keyword, genre, popularity, and vote-average signals. The result is sorted and the top ten are returned.

### Actual implementation

1. **Source dataset:** `backend/dumped_obj/movie_dataframe_for_app.csv`, loaded in `backend/app.py` as `dataframe`. It currently has 1,368 rows and 23 CSV columns, plus the saved `index` column in the dataframe file.
2. **Columns:** `index`, budget, genres, id, keywords, original_language, original_title, overview, popularity, production_companies, release_date, revenue, runtime, spoken_languages, tagline, vote_average, vote_count, cast, crew, weighted_avg, weighted_avg_scaled, popularity_scaled, and score_mix.
3. **Preprocessing in runtime ranking:** `app.py` parses serialized genres, keywords, cast, and crew; handles missing numeric values; normalizes popularity and vote counts; creates title tokens; and derives genre/cast/director sets.
4. **TF-IDF text:** `SimilarityService.build_combined_features` fills missing overview, genres, keywords, cast, and crew with empty strings and concatenates them. `TfidfVectorizer(stop_words="english")` vectorizes the result.
5. **Metadata artifact generation:** `SimilarityService.generate_similarity_matrix` calls `sklearn.metrics.pairwise.sigmoid_kernel`, and `rebuild_similarity.py` writes `dumped_obj/sigmoid_kernel.pkl`.
6. **Semantic text:** `EmbeddingService.TEXT_COLUMNS` are collection, original_title, genres, keywords, tagline, and overview. Missing values become empty strings, each row becomes one space-separated text string, and no rows are filtered or deduplicated.
7. **Semantic model:** `EmbeddingService` loads Sentence Transformers model `all-MiniLM-L6-v2` and calls `model.encode(..., convert_to_numpy=True)`. The regenerated output is 1,368 by 384.
8. **Semantic similarity:** `SemanticSimilarityService.similarity_scores` computes cosine similarity from the embedding matrix, excludes the selected row by setting its score to `-1`, and returns finite scores keyed by positional dataframe index.
9. **Hybrid ranking:** `HybridRankingService.recommend` takes the top 100 metadata and semantic candidates, adds franchise/title candidates, optionally filters by genre, normalizes candidate values, calculates weighted parts, sorts descending, and returns ten items.
10. **Weights:** semantic 0.45; metadata 0.25; collection 0.10; keyword 0.10; popularity 0.05; vote average 0.05. Genre overlap modifies the metadata signal, and distinctive genres can reduce metadata influence when absent.
11. **Match score:** `HybridRankingService._match_score` converts the final 0-1 score to an integer from 0 to 99. `app.py` returns that value as `match_score`.
12. **Reasons:** the ranker emits reasons such as same franchise, semantic story similarity, similar genre, shared cast, same director, and popular/high-rated movie.
13. **Explanations:** `ExplanationService` independently parses shared signals and produces a short natural-language explanation. It uses an LRU-like `OrderedDict` cache capped at 2,048 entries.
14. **Selected movie mapping:** `app.py` builds `indices = pd.Series(data.index, index=data["original_title"]).drop_duplicates()`. The exact title maps to the first positional row. That index is used for both artifact arrays and the dataframe.
15. **Frontend response:** `app.recommend` enriches each result by title through TMDB search, then merges the TMDB card data with the local score, reasons, and explanation. `Home` displays the response and stores a reduced copy in history.

### Generated artifacts

| Artifact | Current shape/content | Purpose | Alignment requirement |
|---|---|---|---|
| `backend/dumped_obj/semantic_embeddings.pkl` | NumPy matrix `(1368, 384)` | One semantic vector per dataframe row. | Row `n` must describe dataframe row `n`. |
| `backend/dumped_obj/embedding_metadata.json` | Model `all-MiniLM-L6-v2`, dimension 384, movie count 1368 | Human/tool metadata for the embedding artifact. | `movie_count` should equal the dataframe length. |
| `backend/dumped_obj/sigmoid_kernel.pkl` | Similarity matrix `(1368, 1368)` | Fast metadata similarity lookup for every movie pair. | Both matrix axes must use the same dataframe order. |

The artifacts have no independent movie-ID index. A row-count check prevents the application from silently using incorrect positional alignment. The current artifacts have matching dimensions and the production app imports successfully.

## 5. Backend Architecture

```text
app.py
├── loads CSV data and generated artifacts
├── parses catalogue fields and builds lookup signals
├── FastAPI routes
│   ├── /health
│   ├── /movies, /search, /genres
│   ├── /trending, /movie/{tmdb_id}
│   └── /recommend/{movie_title}
├── HybridRankingService
│   ├── SemanticSimilarityService -> semantic_embeddings.pkl
│   └── sigmoid_kernel.pkl
├── ExplanationService
└── direct TMDB request helpers

maintenance scripts
├── DatasetService -> catalogue CSV files
├── TMDBService -> catalogue updates
├── SimilarityService -> sigmoid_kernel.pkl
└── EmbeddingService -> semantic_embeddings.pkl + metadata
```

| Service/file | Responsibility | Inputs | Outputs | Callers |
|---|---|---|---|---|
| `backend/app.py` | Application composition, route handlers, parsing, enrichment | CSVs, artifacts, HTTP parameters | FastAPI JSON responses | Frontend and benchmark scripts |
| `services/hybrid_ranking_service.py` | Candidate selection and weighted ranking | dataframe, metadata matrix, semantic service | Ranked index/title/score/reasons/parts | `/recommend` |
| `services/semantic_similarity_service.py` | Load/validate embeddings and cosine scores | dataframe and `semantic_embeddings.pkl` | similarity scores | Hybrid ranker |
| `services/similarity_service.py` | Build TF-IDF and sigmoid metadata matrix | dataframe CSV | `sigmoid_kernel.pkl` | `rebuild_similarity.py`, catalogue maintenance |
| `services/embedding_service.py` | Build semantic vectors and metadata | dataframe CSV, Sentence Transformer model | embedding pickle and JSON metadata | direct script and GitHub Actions |
| `services/explanation_service.py` | Human-readable recommendation explanations | two dataframe rows and signals | explanation string | `/recommend` |
| `services/dataset_service.py` | Add/update catalogue rows and save both CSVs | existing dataframe and movie dictionaries | updated CSVs and stats | update scripts |
| `services/tmdb_service.py` | TMDB client for maintenance workflows | API key, endpoints | raw TMDB data and normalized movie rows | catalogue scripts |
| `services/recommendation_service.py` | None | None | None | Appears unused; file is empty |

There are no backend routers, Pydantic request/response schemas, ORM models, database layer, or authentication layer. FastAPI serves OpenAPI/Swagger/ReDoc automatically.

## 6. API Documentation

| Method | Endpoint | Purpose | Parameters | Response | Frontend usage |
|---|---|---|---|---|---|
| GET | `/health` | Health check | None | `{"status":"ok"}` | Not called by frontend; useful for deployment checks |
| GET | `/movies` | Return all catalogue titles | None | JSON list of strings | Not called; likely legacy/unused |
| GET | `/search` | Catalogue title autocomplete | `query` query string | `{"results":[...]}` | `Home` |
| GET | `/genres` | Available catalogue genres | None | `{"genres":[...]}` | `Home` |
| GET | `/trending` | TMDB daily trending movies | None | `{"results":[movie cards]}` | `Home` |
| GET | `/recommend/{movie_title}` | Hybrid recommendations | URL title; optional `genre` query parameter | `{"movie":...,"recommendations":[...]}` or local `error` field | `Home` |
| GET | `/movie/{tmdb_id}` | Detailed TMDB movie page | integer path ID | normalized details, cast, trailer, images | `MovieDetails` |

FastAPI also exposes `/docs`, `/redoc`, `/openapi.json`, and `/docs/oauth2-redirect`; these are framework-generated.

Potentially unused/incomplete API surface:

- `/movies` is not used by the frontend; search uses the in-memory title list through `/search`.
- `recommendation_service.py` is empty and is not part of the actual recommendation path.
- `/recommend` returns `{"error":"Movie not found"}` with HTTP 200 for an unknown title, unlike its HTTP error responses for invalid genres and infrastructure failures.
- Search is catalogue-only, while recommendation enrichment is a separate TMDB search by title.

## 7. Frontend Architecture

- `frontend/src/main.jsx` is the entry point and installs `BrowserRouter`.
- `frontend/src/App.jsx` owns route declarations, the home search/recommendation UI, shared navigation, movie cards, saved collection pages, loading states, and error states.
- `frontend/src/MovieDetails.jsx` owns `/movie/:id` data fetching, detail rendering, and recently-viewed recording.
- `frontend/src/Dashboard.jsx` owns browser activity analytics and dashboard presentation.
- `frontend/src/NotFound.jsx` handles unmatched routes.
- `frontend/src/useMovieActivity.js` owns recently viewed and recommendation history state/persistence.
- `frontend/src/useMovieCollections.js` owns favorites and watchlist state/persistence.
- `frontend/src/config.js` creates the Axios client and defines local/production API base URLs.
- CSS is split between `App.css`, `Dashboard.css`, `MovieDetails.css`, and `index.css`. The UI includes skeleton loaders, responsive layouts, accessible labels, and reduced-motion-aware recommendation scrolling.
- There is no global state library, backend user account, or server-side session.

Routes:

```text
/             Home and recommendations
/favorites    Saved favorites
/watchlist    Saved watchlist
/dashboard    Browser activity dashboard
/movie/:id    TMDB movie details
*             NotFound
```

## 8. Data Flow

Catalogue and ML flow:

```text
TMDB catalogue/update scripts
  -> DatasetService
  -> movie_dataframe_for_app.csv and movie_data_for_app.csv
  -> SimilarityService -> sigmoid_kernel.pkl
  -> EmbeddingService -> semantic_embeddings.pkl + embedding_metadata.json
  -> app.py loads all artifacts at import time
  -> HybridRankingService and SemanticSimilarityService
  -> /recommend JSON
  -> React movie cards and local history
```

Runtime TMDB flow:

```text
React /trending or /movie/:id request
  -> FastAPI route
  -> requests.get with TMDB_API_KEY
  -> normalized response
  -> React card/detail state
```

Recommendation enrichment also calls TMDB `/search/movie` for each recommended title in a five-worker thread pool. This means recommendation availability and card IDs depend partly on TMDB, even though ranking itself is local.

## 9. Local Storage

| Key | Purpose | Data stored | Used by |
|---|---|---|---|
| `favorites` | Saved favorite movies | Normalized movie cards with ID, title, images, release date, rating, overview | `useMovieCollections.js`, `App.jsx`, `Dashboard.jsx` |
| `watchlist` | Saved watchlist movies | Same normalized movie-card structure | `useMovieCollections.js`, `App.jsx`, `Dashboard.jsx` |
| `recentlyViewed` | Last viewed details | Up to ten normalized movies, deduplicated by ID | `useMovieActivity.js`, `App.jsx`, `Dashboard.jsx` |
| `recommendationHistory` | Successful recommendation searches | Up to ten unique title/genre entries, timestamps, recommendation cards, scores, reasons, explanations | `useMovieActivity.js`, `App.jsx`, `Dashboard.jsx` |

Both hooks catch JSON parsing and storage exceptions. They also listen for the browser `storage` event, so changes from another tab can be reflected. LocalStorage is not suitable for secrets; this application stores movie activity only.

## 10. TMDB Integration

Production runtime calls are in `backend/app.py`:

- `/search/movie` is used by `search_tmdb_movie` to enrich recommendation cards.
- `/trending/movie/day` is used by `/trending`.
- `/movie/{id}` with `append_to_response=credits,videos` is used by `/movie/{tmdb_id}`.

Maintenance calls are in `backend/services/tmdb_service.py`, including popular, now playing, upcoming, top rated, changes, movie details, credits, keywords, and collection/discovery calls through the catalogue scripts.

The backend reads `TMDB_API_KEY` from environment configuration. The repository contains an ignored backend `.env`; its value was not exposed in this report. The frontend does not receive the TMDB key. Images and trailers are returned as public TMDB/YouTube URLs.

When TMDB fails:

- Search enrichment falls back to a title-only card.
- Details and trending return HTTP 503/404/502 errors with human-readable details.
- The frontend renders recommendation errors, trending error states, or movie-detail error pages.
- Catalogue maintenance catches several TMDB failures and skips affected records.

## 11. Deployment Status

### Frontend

`frontend/vercel.json` rewrites every path to `/`, allowing client-side React Router navigation on Vercel. `frontend/package.json` defines `npm run build` and Vite outputs to the default `dist/` directory. `frontend/src/config.js` uses `VITE_API_BASE_URL` when present, otherwise local `http://127.0.0.1:8000` in development and a hardcoded Render URL in production.

The frontend `.env` contains a local API URL and is ignored by Git. No tracked Vercel project configuration or environment declaration was found beyond the rewrite file.

### Backend

No Dockerfile, Procfile, Render manifest, or other tracked backend platform configuration was found. The README documents manual Uvicorn startup. The assumed production backend URL is hardcoded in the frontend config.

The GitHub Actions workflow `.github/workflows/update-movie-catalogue.yml` runs on a weekly schedule or manually, installs backend requirements, updates the catalogue, rebuilds the similarity matrix and embeddings, validates dimensions, and commits generated artifacts. This is a data-maintenance workflow, not backend deployment.

### Consistency concerns

- Local frontend config points to localhost; production fallback points to Render.
- The backend `.env` has `FRONTEND_URL` written with an extra `=` before the URL. Because the code uses `load_dotenv` and then uses the value for CORS, this likely produces an incorrect allowed production origin. The local regex still allows localhost.
- No documented backend deployment command or health-check integration was found.
- The hardcoded production URL makes environment changes require a frontend source change unless `VITE_API_BASE_URL` is configured during build.

## 12. Error Handling

### Present

- Backend startup validates artifact dimensions and fails rather than silently misaligning rows.
- Semantic, metadata, TMDB HTTP, request, JSON, and missing-key cases have targeted handling.
- React recommendation, search, trending, and detail requests have loading, cancellation, error, and empty states.
- AbortController is used for changing search requests, initial home requests, detail navigation, and recommendation cancellation.
- LocalStorage parsing and write failures are caught.
- Skeleton loading UIs exist for the home, dashboard, and detail surfaces.

### Missing or weak

- No React error boundary protects against render-time exceptions.
- App initialization is import-time and a missing/corrupt artifact prevents all backend routes from starting.
- `get_tmdb_movie_details` can raise `HTTPException` for missing keys, but no health endpoint reports dependency/artifact readiness.
- The `/recommend` unknown-title path uses HTTP 200 with an error object, forcing clients to inspect payload shape.
- `MovieDetails` does not set a dedicated error state for cancellation, which is acceptable for navigation but not observable.
- No retry control is provided for failed search/trending/details requests beyond refreshing or trying again.
- The dashboard has no independent error boundary because it uses only local data.

## 13. Security Review

No changes were made during this review.

- **Secret exposure risk:** the ignored backend `.env` contains a TMDB key locally. It was not printed here. Confirm that it is not tracked and rotate it if it has ever been committed or shared.
- **CORS risk/configuration bug:** CORS allows the configured frontend origin plus localhost regex. The current `.env` formatting appears to make the production origin value incorrect. `allow_credentials=True` is enabled even though there is no cookie authentication.
- **API key handling:** the key is kept server-side in normal runtime code, which is correct. TMDB calls use query-string keys, so server/proxy logs must be treated as sensitive.
- **LocalStorage:** saved movie metadata and recommendation history are readable and mutable by any script running in the origin. No secrets are stored there, but the data is user-local and unencrypted.
- **Injection:** recommendation title is URL-encoded by the frontend. Backend dataframe values are returned as JSON. No SQL layer exists. React escapes rendered text by default. External trailer links use `target="_blank"` with `rel="noreferrer"`.
- **Error disclosure:** most errors are deliberately generic. Raw exception details are not generally returned.
- **Unnecessary exposure:** FastAPI docs and `/movies` are publicly available by default. This may be acceptable for a student project but should be considered for production.
- **Authentication/authorization:** not implemented. All activity is browser-local and there are no accounts or private server data.

## 14. Code Quality

### High priority

- Production CORS configuration should be corrected and verified against the deployed frontend origin; the extra `=` in `backend/.env` is a concrete configuration defect.
- There is no automated API/integration test suite for the seven routes, TMDB failure paths, artifact alignment, or frontend behavior.
- Recommendation card enrichment searches TMDB by title rather than carrying the catalogue movie ID. Duplicate titles and title changes can produce a different TMDB movie ID than the ranked catalogue row.
- The recommendation lookup is exact-title based and `indices` keeps only the first duplicate title. The dataset has duplicate titles, so a user cannot select a specific duplicate from the title-only search contract.
- The backend has no deployment manifest or documented production startup configuration, making deployment reproducibility weak.

### Medium priority

- Recommendation logic and data parsing are concentrated in `app.py`, making the main module large and import-heavy.
- `services/recommendation_service.py` is empty and confusing because the actual logic lives in `app.py` and `hybrid_ranking_service.py`.
- `TMDBService` and runtime `app.py` use separate TMDB clients and error policies, creating duplicated integration behavior.
- `SimilarityService.build_combined_features` mutates its dataframe argument by adding columns; this is harmless for the script's local dataframe but surprising for reuse.
- `/movies` appears unused and the README does not document the actual API contract.
- The dashboard derives analytics on each render; the current ten-item limits make this small, but a server-backed history would need a different approach.
- Recommendation calls can make up to ten TMDB title searches per request, even though ranking is local. Caching reduces repeated work but cold requests can be network-heavy.
- Generated pickle artifacts are executable Python serialization and should only be loaded from trusted repository-controlled files.

### Low priority

- Several SVG icons are duplicated across `App.jsx`, `Dashboard.jsx`, and `MovieDetails.jsx`.
- Frontend state and rendering are concentrated in `App.jsx`.
- The frontend README is still the stock Vite template and does not describe CineMatch.
- Benchmark scripts write result files when run and are not tests; their output artifacts are not part of the normal app path.
- Some backend modules and legacy scripts overlap in purpose (`update_movies.py`, `scripts/incremental_update.py`, `scripts/expand_dataset.py`, `scripts/catalogue_builder.py`).

## 15. What Is Actually Completed

### Completed

- React/Vite application with client-side routes.
- Catalogue title search and autocomplete.
- Genre discovery and filtering.
- Hybrid metadata plus semantic recommendations.
- Regenerated and dimension-aligned ML artifacts for 1,368 movies.
- Recommendation scores, reasons, and explanations.
- TMDB detail and trending integrations.
- Favorites, watchlist, recently viewed, and recommendation history in localStorage.
- Dashboard analytics over local activity.
- Loading, empty, and several error states.
- Automated GitHub catalogue/artifact refresh workflow.
- Frontend lint check passed during this audit.
- Backend import/startup artifact check passed during this audit.

### Partially completed or needs verification

- Production deployment configuration and backend hosting reproducibility.
- CORS configuration for the deployed frontend.
- Responsive and accessibility verification on real browsers/devices.
- Automated test coverage beyond the small recommendation smoke script and benchmark utilities.
- Production TMDB behavior, because it requires a valid external key and network.

### Not implemented

- User accounts, authentication, authorization, or server-side profiles.
- Database persistence.
- Cross-device synchronization.
- Admin UI for catalogue/model management.
- Formal API schemas or versioning.

## 16. Recommended Development Roadmap

1. Fix and verify production CORS/environment configuration, then test local and deployed frontend-to-backend requests.
2. Add focused backend tests for artifact dimensions, search, genre validation, recommendation response shape, duplicate-title behavior, and TMDB failures.
3. Add frontend tests or browser smoke tests for routing, search, recommendation, save/remove, details, and localStorage restoration.
4. Make recommendation identity ID-based end to end where possible, avoiding title-only TMDB enrichment and duplicate-title ambiguity.
5. Add a reproducible backend deployment manifest/startup guide and a health/readiness check that validates artifacts and TMDB configuration separately.
6. Refactor route logic from `app.py` into routers/services only after tests protect current behavior.
7. Replace the stock frontend README with project-specific setup, environment, API, and deployment documentation.
8. Measure cold/warm recommendation latency and decide whether TMDB enrichment needs batching, stronger caching, or local metadata fallback.
9. Perform browser-based responsive/accessibility/security verification.
10. Consider accounts/database only if cross-device persistence becomes a real product requirement.

## 17. Top 10 Things to Understand First

1. **`backend/app.py`:** This is the composition root and currently owns startup, routes, lookup tables, parsing, scoring helpers, and TMDB enrichment. Understanding it explains most runtime behavior.
2. **`HybridRankingService.recommend`:** This is the central ranking algorithm. Learn how candidate pools, normalization, weights, filters, and tie-breaking become the final order.
3. **Positional artifact alignment:** `dataframe.iloc[index]`, embedding row `index`, and similarity row/column `index` must refer to the same movie. This is the most important ML correctness invariant.
4. **`EmbeddingService`:** Learn how the six text fields become one string and how `all-MiniLM-L6-v2` turns it into a 384-dimensional vector.
5. **`SimilarityService`:** Learn TF-IDF, the sigmoid kernel, and why the matrix is square and tied to dataframe order.
6. **`DatasetService` and catalogue scripts:** These determine when rows are added or updated and when artifacts need rebuilding.
7. **`/recommend/{movie_title}`:** Follow the full request from title lookup to ranker, TMDB enrichment, explanation, and JSON response.
8. **`useMovieActivity.js` and `useMovieCollections.js`:** These are the complete persistence layer for the current product. Learn normalization, deduplication, limits, and storage failure handling.
9. **`App.jsx` route and component structure:** It contains the main product workflows and shows how API state becomes cards, history, and collections.
10. **Environment and deployment configuration:** `backend/.env`, `frontend/.env`, `frontend/src/config.js`, `frontend/vercel.json`, and the GitHub workflow explain why local and deployed behavior can differ.

## 18. Final Project Map

```text
FRONTEND
├── src/main.jsx             React entry point and BrowserRouter
├── src/App.jsx              Home, routes, cards, collections, recommendations
├── src/MovieDetails.jsx     TMDB movie details page
├── src/Dashboard.jsx        Browser activity dashboard
├── src/useMovieActivity.js  Recently viewed and recommendation history
├── src/useMovieCollections.js Favorites and watchlist
├── src/config.js            Axios client and API base URL
└── *.css                    UI styling and responsive layout

BACKEND
├── app.py                   FastAPI app, routes, parsing, enrichment
├── services/dataset_service.py
├── services/tmdb_service.py Catalogue maintenance TMDB client
├── services/similarity_service.py
├── services/embedding_service.py
├── services/semantic_similarity_service.py
├── services/hybrid_ranking_service.py
├── services/explanation_service.py
└── rebuild_similarity.py    Metadata artifact rebuild entry point

ML
├── Dataset                 dumped_obj/movie_dataframe_for_app.csv
├── Semantic embeddings     dumped_obj/semantic_embeddings.pkl (1368 x 384)
├── Embedding metadata      dumped_obj/embedding_metadata.json
├── Metadata similarity     dumped_obj/sigmoid_kernel.pkl (1368 x 1368)
└── Ranking                 HybridRankingService

EXTERNAL SERVICES
├── TMDB API                Search, trending, details, credits, videos
├── YouTube                 Trailer links returned by TMDB
├── Vercel                  Frontend routing/deployment configuration
└── Render                  Production API URL assumed by frontend config
```

### Completion estimate

These are functional-scope estimates, not file-count estimates:

- Frontend: **85%**
- Backend: **80%**
- ML/recommendation: **85%**
- Testing: **30%**
- Deployment: **55%**
- Overall: **72%**

The estimates treat the existing user-facing features as implemented while discounting missing production verification, tests, accounts, database persistence, and deployment reproducibility.

## If I Were Continuing This Project Tomorrow

1. Correct and verify the CORS/environment configuration, because production frontend requests may currently be rejected.
2. Add a small route and artifact-validation test suite, because the application loads critical ML files at startup and currently has little automated protection.
3. Trace one recommendation with a duplicate title and change enrichment to preserve catalogue identity, because title-only lookup can return the wrong TMDB movie.
4. Add a browser smoke test for home, search, recommendation, details, favorites, watchlist, and dashboard flows.
5. Write project-specific setup and deployment documentation, because the current frontend README is still the Vite template and backend deployment configuration is implicit.
