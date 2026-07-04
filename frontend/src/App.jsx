import { useEffect, useState } from "react";
import axios from "axios";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import MovieDetails from "./MovieDetails";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function FilmIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6.5h16v11H4zM8 6.5v11M16 6.5v11M4 10h4m8 0h4M4 14h4m8 0h4M7 3.5l2 3m3-3 2 3m3-3 2 3" />
    </svg>
  );
}

function SparkleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.75c.45 4.8 2.7 7.05 7.5 7.5-4.8.45-7.05 2.7-7.5 7.5-.45-4.8-2.7-7.05-7.5-7.5 4.8-.45 7.05-2.7 7.5-7.5ZM19 16.25c.18 1.87 1.13 2.82 3 3-1.87.18-2.82 1.13-3 3-.18-1.87-1.13-2.82-3-3 1.87-.18 2.82-1.13 3-3Z" />
    </svg>
  );
}

function MovieCard({ movie }) {
  const releaseYear = movie.release_date
    ? movie.release_date.slice(0, 4)
    : "Year unavailable";
  const rating =
    typeof movie.vote_average === "number"
      ? movie.vote_average.toFixed(1)
      : "NR";

  const content = (
    <>
      <div className="poster-art">
        {movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt={`${movie.title} poster`}
            loading="lazy"
          />
        ) : (
          <div
            className="no-poster"
            role="img"
            aria-label="No poster available"
          >
            <FilmIcon />
            <span>No Poster</span>
          </div>
        )}
      </div>
      <div className="movie-details">
        <h3 title={movie.title}>{movie.title}</h3>
        <div className="movie-meta">
          <span>{releaseYear}</span>
          <span aria-label={`TMDB rating ${rating} out of 10`}>
            <b aria-hidden="true">★</b> {rating}
          </span>
        </div>
        {movie.overview && <p className="movie-overview">{movie.overview}</p>}
        <span className="card-action">
          {movie.id ? "View details →" : "Details unavailable"}
        </span>
      </div>
    </>
  );

  return movie.id ? (
    <Link
      className="movie-card movie-card-link"
      to={`/movie/${movie.id}`}
      aria-label={`View details for ${movie.title}`}
    >
      {content}
    </Link>
  ) : (
    <article className="movie-card">{content}</article>
  );
}

function Home() {
  const [movies, setMovies] = useState([]);
  const [selectedMovie, setSelectedMovie] = useState("");
  const [recommendations, setRecommendations] = useState([]);
  const [isLoadingMovies, setIsLoadingMovies] = useState(true);
  const [isRecommending, setIsRecommending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    axios
      .get(`${API_URL}/movies`)
      .then((res) => setMovies(res.data))
      .catch(() => setError("We couldn't load the movie library. Please try again."))
      .finally(() => setIsLoadingMovies(false));
  }, []);

  const getRecommendations = async (event) => {
    event.preventDefault();

    if (!selectedMovie) return;

    setIsRecommending(true);
    setError("");

    try {
      const res = await axios.get(
        `${API_URL}/recommend/${encodeURIComponent(selectedMovie)}`,
      );
      setRecommendations(res.data.recommendations || []);
    } catch {
      setError("Something interrupted the search. Please give it another try.");
    } finally {
      setIsRecommending(false);
    }
  };

  return (
    <main className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel">
        <header className="hero-copy">
          <div className="brand-mark" aria-hidden="true">
            <FilmIcon />
          </div>
          <p className="eyebrow">
            <span /> Curated for your next movie night
          </p>
          <h1>
            Find a film you’ll <span>love.</span>
          </h1>
          <p className="hero-description">
            Choose a movie you already enjoy and discover your next favorite in
            seconds.
          </p>
        </header>

        <form className="movie-search" onSubmit={getRecommendations}>
          <label htmlFor="movie-select">Start with a movie</label>
          <div className="search-controls">
            <div className="select-wrap">
              <FilmIcon />
              <select
                id="movie-select"
                value={selectedMovie}
                onChange={(event) => setSelectedMovie(event.target.value)}
                disabled={isLoadingMovies}
              >
                <option value="">
                  {isLoadingMovies ? "Loading movies…" : "Select a movie"}
                </option>
                {movies.map((movie) => (
                  <option key={movie} value={movie}>
                    {movie}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={!selectedMovie || isRecommending}
            >
              {isRecommending ? (
                <span className="spinner" aria-hidden="true" />
              ) : (
                <SparkleIcon />
              )}
              {isRecommending ? "Finding matches…" : "Recommend"}
            </button>
          </div>
        </form>

        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}

        <section className="results" aria-live="polite">
          <div className="results-heading">
            <div>
              <p className="section-kicker">Made for you</p>
              <h2>Your recommendations</h2>
            </div>
            {recommendations.length > 0 && (
              <span className="result-count">
                {recommendations.length} movies
              </span>
            )}
          </div>

          {recommendations.length > 0 ? (
            <div className="movie-grid">
              {recommendations.map((movie, index) => (
                <MovieCard
                  movie={movie}
                  key={`${movie.id || movie.title}-${index}`}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">
                <SparkleIcon />
              </div>
              <div>
                <h3>Your watchlist starts here</h3>
                <p>Select a movie above to reveal recommendations.</p>
              </div>
            </div>
          )}
        </section>
      </section>

      <footer>
        <FilmIcon />
        <span>Thoughtful picks, one movie at a time.</span>
      </footer>
    </main>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/movie/:id" element={<MovieDetails />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
