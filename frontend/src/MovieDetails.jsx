import { useEffect, useState } from "react";
import axios from "axios";
import { Link, useParams } from "react-router-dom";
import "./MovieDetails.css";

const API_URL = "http://127.0.0.1:8000";

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m15 18-6-6 6-6M9 12h11" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9 7 8 5-8 5V7Z" />
    </svg>
  );
}

function FilmIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6.5h16v11H4zM8 6.5v11M16 6.5v11M4 10h4m8 0h4M4 14h4m8 0h4M7 3.5l2 3m3-3 2 3m3-3 2 3" />
    </svg>
  );
}

function PersonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0" />
    </svg>
  );
}

function formatRuntime(runtime) {
  if (!runtime) return "Runtime unavailable";

  const hours = Math.floor(runtime / 60);
  const minutes = runtime % 60;
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function MovieDetails({ onMovieViewed }) {
  const { id } = useParams();
  const hasValidId = /^\d+$/.test(id || "");
  const [requestState, setRequestState] = useState({
    id: null,
    movie: null,
    error: "",
  });

  const isLoading = hasValidId && requestState.id !== id;
  const movie = requestState.id === id ? requestState.movie : null;
  const error = requestState.id === id ? requestState.error : "";

  useEffect(() => {
    const controller = new AbortController();

    if (!hasValidId) {
      return () => controller.abort();
    }

    axios
      .get(`${API_URL}/movie/${id}`, { signal: controller.signal })
      .then((response) => {
        setRequestState({ id, movie: response.data, error: "" });
        onMovieViewed(response.data);
      })
      .catch((requestError) => {
        if (requestError.code !== "ERR_CANCELED") {
          const detail = requestError.response?.data?.detail;
          setRequestState({
            id,
            movie: null,
            error:
              typeof detail === "string"
                ? detail
                : "We couldn't load this movie right now.",
          });
        }
      });

    return () => controller.abort();
  }, [hasValidId, id, onMovieViewed]);

  useEffect(() => {
    if (!movie?.title) return undefined;

    const previousTitle = document.title;
    document.title = `${movie.title} — CineMatch`;
    return () => {
      document.title = previousTitle;
    };
  }, [movie]);

  const displayError = hasValidId
    ? error || "We couldn't find that movie."
    : "That movie link is not valid.";

  if (!hasValidId || (!isLoading && (error || !movie))) {
    return (
      <main className="details-state-page">
        <div className="details-error" role="alert">
          <div className="details-error-icon">
            <FilmIcon />
          </div>
          <p className="details-kicker">Something went off script</p>
          <h1>Movie details unavailable</h1>
          <p>{displayError}</p>
          <Link className="details-button details-button-secondary" to="/">
            <ArrowLeftIcon /> Back to Home
          </Link>
        </div>
      </main>
    );
  }

  if (isLoading) {
    return (
      <main className="details-state-page">
        <div className="details-loader" role="status">
          <span className="details-spinner" aria-hidden="true" />
          <h1>Setting the scene…</h1>
          <p>Loading movie details</p>
        </div>
      </main>
    );
  }

  const releaseYear = movie.release_date?.slice(0, 4) || "Year unavailable";
  const rating =
    typeof movie.vote_average === "number"
      ? movie.vote_average.toFixed(1)
      : "NR";

  return (
    <main className="details-page">
      <section className="details-hero">
        {movie.backdrop_url && (
          <img
            className="details-backdrop"
            src={movie.backdrop_url}
            alt=""
            aria-hidden="true"
          />
        )}
        <div className="details-backdrop-shade" />

        <nav className="details-nav details-container" aria-label="Movie navigation">
          <Link className="back-link" to="/">
            <ArrowLeftIcon /> Back to Home
          </Link>
          <div className="details-nav-right">
            <Link className="details-nav-link" to="/favorites">
              Favorites
            </Link>
            <Link className="details-nav-link" to="/watchlist">
              Watchlist
            </Link>
            <Link className="details-nav-link" to="/dashboard">
              Dashboard
            </Link>
            <span className="details-brand">
              <FilmIcon /> CineMatch
            </span>
          </div>
        </nav>

        <div className="details-layout details-container">
          <div className="details-poster">
            {movie.poster_url ? (
              <img src={movie.poster_url} alt={`${movie.title} poster`} />
            ) : (
              <div className="details-poster-placeholder">
                <FilmIcon />
                <span>No Poster</span>
              </div>
            )}
          </div>

          <div className="details-copy">
            <p className="details-kicker">Now showing</p>
            <h1>{movie.title}</h1>

            <div className="details-facts" aria-label="Movie facts">
              <span>{releaseYear}</span>
              <span>{formatRuntime(movie.runtime)}</span>
              <span className="details-rating">
                <b aria-hidden="true">★</b> {rating} <small>/ 10</small>
              </span>
            </div>

            {movie.genres.length > 0 && (
              <div className="genre-list" aria-label="Genres">
                {movie.genres.map((genre) => (
                  <span key={genre}>{genre}</span>
                ))}
              </div>
            )}

            <p className="details-overview">
              {movie.overview || "No overview is available for this movie."}
            </p>

            <div className="director-line">
              <span>Director</span>
              <strong>{movie.director || "Not available"}</strong>
            </div>

            <div className="details-actions">
              {movie.trailer_url && (
                <a
                  className="details-button details-button-primary"
                  href={movie.trailer_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <PlayIcon /> Watch Trailer
                </a>
              )}
              <Link className="details-button details-button-secondary" to="/">
                <ArrowLeftIcon /> Back to Home
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="cast-section details-container">
        <div className="cast-heading">
          <div>
            <p className="details-kicker">Meet the faces</p>
            <h2>Top cast</h2>
          </div>
          <span>{movie.cast.length} cast members</span>
        </div>

        {movie.cast.length > 0 ? (
          <div className="cast-grid">
            {movie.cast.map((member, index) => (
              <article className="cast-card" key={`${member.name}-${index}`}>
                <div className="cast-photo">
                  {member.profile_url ? (
                    <img
                      src={member.profile_url}
                      alt={member.name}
                      loading="lazy"
                    />
                  ) : (
                    <div className="cast-placeholder">
                      <PersonIcon />
                    </div>
                  )}
                </div>
                <div className="cast-copy">
                  <h3>{member.name}</h3>
                  <p>{member.character || "Character unavailable"}</p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="cast-empty">Cast information is not available.</div>
        )}
      </section>
    </main>
  );
}

export default MovieDetails;
