# 🎬 CineMatch – Movie Recommendation System

A full-stack Movie Recommendation System powered by Machine Learning and TMDB metadata. Users can search movies, receive personalized recommendations with similarity scores, explore trending movies, manage favorites and watchlists, and view detailed movie information.

## 🌐 Live Demo

### Frontend
https://movie-recommendation-system-nu-pearl.vercel.app



---

# ✨ Features

## 🎯 Smart Movie Recommendations

- Machine Learning based recommendation engine
- Similarity score (match percentage) for every recommendation
- Recommendation explanation
- Genre filtering
- Top 10 personalized recommendations
- Preserves original recommendation ranking

---

## 🔍 Movie Search

- Fast autocomplete
- Case-insensitive search
- Prefix prioritization
- Instant suggestions

---

## 🎞 Movie Details

- High-resolution backdrop
- Movie poster
- Overview
- Release year
- Runtime
- Genres
- Director
- Top cast
- TMDB rating
- YouTube trailer

---

## 🔥 Trending Movies

Daily trending movies powered by TMDB.

---

## ❤️ Favorites

- Add/remove favorites
- Stored in LocalStorage
- Persistent across refresh

---

## 📌 Watchlist

- Add/remove watchlist
- Duplicate prevention
- Persistent storage

---

## 🕒 Recently Viewed

- Automatically records viewed movies
- Latest 10 movies
- Quick access from Home page

---

## 📈 Recommendation History

- Stores previous recommendation searches
- Restore previous recommendations
- Delete individual history
- Clear all history

---

## 📊 Dashboard

Displays user activity including:

- Favorite count
- Watchlist count
- Recently viewed
- Search history
- Most searched movies
- Top recommendation scores
- Genre usage statistics

---

# 🧠 Recommendation Engine

The recommendation engine uses **Content-Based Filtering** built with **Scikit-learn**.

Movie similarity is calculated using:

- Genres
- Keywords
- Cast
- Director
- Story overview

The application uses a precomputed similarity matrix (`sigmoid_kernel.pkl`) for fast recommendations.

---

# 🛠 Tech Stack

## Frontend

- React 19
- Vite
- React Router
- Axios
- CSS

## Backend

- FastAPI
- Pandas
- NumPy
- Scikit-learn
- Joblib

## External API

- TMDB API

## Deployment

- Vercel
- Render

---

# 📁 Project Structure

```
movie_recommendation_system
│
├── backend
│   ├── app.py
│   ├── requirements.txt
│   ├── dumped_obj/
│   └── ...
│
├── frontend
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── DEPLOYMENT.md
└── README.md
```

---

# 🚀 Installation

## Clone Repository

```bash
git clone https://github.com/Achintha0626/movie_recommendation_system.git

cd movie_recommendation_system
```

---

## Backend

```bash
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt

uvicorn app:app --reload
```

Backend runs on

```
http://127.0.0.1:8000
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend runs on

```
http://localhost:5173
```

---

# ⚙ Environment Variables

## Backend

Create:

```
backend/.env
```

```env
TMDB_API_KEY=your_tmdb_api_key
FRONTEND_URL=http://localhost:5173
```

---

## Frontend

Create:

```
frontend/.env
```

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

# 📡 API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | /health | Health Check |
| GET | /movies | Movie List |
| GET | /search?query= | Movie Search |
| GET | /genres | Genres |
| GET | /trending | Trending Movies |
| GET | /recommend/{movie} | Recommendations |
| GET | /movie/{tmdb_id} | Movie Details |

---


# 🚀 Deployment

## Backend

Hosted on **Render**

## Frontend

Hosted on **Vercel**

---


---

# 👨‍💻 Author

**Achintha**

GitHub

https://github.com/Achintha0626

---

# ⭐ Support

If you like this project, consider giving it a ⭐ on GitHub!
