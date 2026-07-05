# Deployment

## Render backend

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Environment variables:
  - `TMDB_API_KEY`: your TMDB API key
  - `FRONTEND_URL`: your production Vercel URL, without a trailing slash

## Vercel frontend

- Root directory: `frontend`
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable:
  - `VITE_API_BASE_URL`: your Render backend URL, without a trailing slash

The frontend rewrite in `frontend/vercel.json` sends client-side routes such as
`/movie/:id`, `/favorites`, `/watchlist`, and `/dashboard` to the React app.
