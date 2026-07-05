import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Link, Navigate, NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./Dashboard";
import MovieDetails from "./MovieDetails";
import { API_BASE_URL } from "./config";
import useMovieActivity from "./useMovieActivity";
import useMovieCollections from "./useMovieCollections";
import "./App.css";

const DEFAULT_GENRES = [
  "All",
  "Action",
  "Adventure",
  "Animation",
  "Comedy",
  "Crime",
  "Drama",
  "Fantasy",
  "Horror",
  "Romance",
  "Sci-Fi",
  "Thriller",
];

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

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  );
}

function HeartIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.8 5.8a5.3 5.3 0 0 0-7.5 0L12 7.1l-1.3-1.3a5.3 5.3 0 0 0-7.5 7.5L12 22l8.8-8.7a5.3 5.3 0 0 0 0-7.5Z" />
    </svg>
  );
}

function BookmarkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 3.5h12v17l-6-4-6 4v-17ZM12 7v6M9 10h6" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6" />
    </svg>
  );
}

function SiteNav({ favoritesCount, watchlistCount }) {
  const navClass = ({ isActive }) =>
    `site-nav-link ${isActive ? "is-active" : ""}`;

  return (
    <nav className="site-nav" aria-label="Main navigation">
      <Link className="site-brand" to="/">
        <span className="site-brand-icon">
          <FilmIcon />
        </span>
        <span>CineMatch</span>
      </Link>
      <div className="site-nav-links">
        <NavLink className={navClass} to="/" end>
          Home
        </NavLink>
        <NavLink className={navClass} to="/favorites">
          Favorites
          {favoritesCount > 0 && <span>{favoritesCount}</span>}
        </NavLink>
        <NavLink className={navClass} to="/watchlist">
          Watchlist
          {watchlistCount > 0 && <span>{watchlistCount}</span>}
        </NavLink>
        <NavLink className={navClass} to="/dashboard">
          Dashboard
        </NavLink>
      </div>
    </nav>
  );
}

function MovieCard({
  movie,
  collections,
  onRemove,
  removeLabel,
  showRecommendationInfo = false,
}) {
  const releaseYear = movie.release_date
    ? movie.release_date.slice(0, 4)
    : "Year unavailable";
  const rating =
    typeof movie.vote_average === "number"
      ? movie.vote_average.toFixed(1)
      : "NR";
  const matchScore =
    typeof movie.match_score === "number"
      ? Math.max(0, Math.min(100, Math.round(movie.match_score)))
      : 0;
  const reasons = Array.isArray(movie.reasons)
    ? movie.reasons.filter((reason) => typeof reason === "string" && reason)
    : [];

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
        {showRecommendationInfo && (
          <div className="recommendation-explanation">
            <div className="match-heading">
              <span className="match-score-badge">{matchScore}% Match</span>
              <span>Why this pick</span>
            </div>
            <div className="reason-chips" aria-label="Recommendation reasons">
              {(reasons.length > 0
                ? reasons
                : ["Similar story overview"]
              ).map((reason) => (
                <span className="reason-chip" key={reason}>
                  {reason}
                </span>
              ))}
            </div>
          </div>
        )}
        <span className="card-action">
          {movie.id ? "View details →" : "Details unavailable"}
        </span>
      </div>
    </>
  );

  const canSave = movie.id != null;
  const favoriteIsActive = canSave && collections.isFavorite(movie.id);
  const watchlistIsActive = canSave && collections.isWatchlisted(movie.id);

  return (
    <article className="movie-card">
      <div className="card-save-actions" aria-label="Save movie">
        <button
          className={`card-save-button favorite-button ${
            favoriteIsActive ? "is-active" : ""
          }`}
          type="button"
          aria-label={
            favoriteIsActive ? "Remove from favorites" : "Add to favorites"
          }
          aria-pressed={favoriteIsActive}
          title={
            canSave
              ? favoriteIsActive
                ? "Remove from favorites"
                : "Add to favorites"
              : "Movie ID unavailable"
          }
          disabled={!canSave}
          onClick={() => collections.toggleFavorite(movie)}
        >
          <HeartIcon />
        </button>
        <button
          className={`card-save-button watchlist-button ${
            watchlistIsActive ? "is-active" : ""
          }`}
          type="button"
          aria-label={
            watchlistIsActive
              ? "Remove from watchlist"
              : "Add to watchlist"
          }
          aria-pressed={watchlistIsActive}
          title={
            canSave
              ? watchlistIsActive
                ? "Remove from watchlist"
                : "Add to watchlist"
              : "Movie ID unavailable"
          }
          disabled={!canSave}
          onClick={() => collections.toggleWatchlist(movie)}
        >
          <BookmarkIcon />
        </button>
      </div>

      {movie.id ? (
        <Link
          className="movie-card-main movie-card-link"
          to={`/movie/${movie.id}`}
          aria-label={`View details for ${movie.title}`}
        >
          {content}
        </Link>
      ) : (
        <div className="movie-card-main">{content}</div>
      )}

      {onRemove && (
        <button
          className="card-remove-button"
          type="button"
          onClick={() => onRemove(movie.id)}
        >
          <TrashIcon /> {removeLabel}
        </button>
      )}
    </article>
  );
}

function MovieCardSkeleton() {
  return (
    <div className="movie-card movie-card-skeleton" aria-hidden="true">
      <div className="skeleton-poster skeleton-shimmer" />
      <div className="skeleton-details">
        <span className="skeleton-line skeleton-title skeleton-shimmer" />
        <span className="skeleton-line skeleton-meta skeleton-shimmer" />
        <span className="skeleton-line skeleton-copy skeleton-shimmer" />
        <span className="skeleton-line skeleton-copy-short skeleton-shimmer" />
      </div>
    </div>
  );
}

function formatRelativeTime(timestamp) {
  const elapsed = Math.max(0, Date.now() - Number(timestamp || 0));
  const minutes = Math.floor(elapsed / 60000);
  const hours = Math.floor(elapsed / 3600000);
  const days = Math.floor(elapsed / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`;
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;

  return new Date(timestamp).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function Home({ activity, collections }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedMovie, setSelectedMovie] = useState("");
  const [searchResponse, setSearchResponse] = useState({
    query: "",
    results: [],
    error: false,
  });
  const [isSuggestionsOpen, setIsSuggestionsOpen] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [trendingState, setTrendingState] = useState({
    status: "loading",
    movies: [],
  });
  const [genreState, setGenreState] = useState({
    status: "loading",
    genres: DEFAULT_GENRES,
  });
  const [selectedGenre, setSelectedGenre] = useState("All");
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationContext, setRecommendationContext] = useState({
    movieTitle: "",
    genre: "All",
  });
  const [isRecommending, setIsRecommending] = useState(false);
  const [error, setError] = useState("");
  const recommendationsRef = useRef(null);
  const shouldScrollToRecommendations = useRef(false);

  const searchQuery = searchTerm.trim();
  const hasCurrentResponse = searchResponse.query === searchQuery;
  const suggestions = hasCurrentResponse ? searchResponse.results : [];
  const isSearching =
    isSuggestionsOpen && Boolean(searchQuery) && !hasCurrentResponse;

  useEffect(() => {
    const controller = new AbortController();

    axios
      .get(`${API_BASE_URL}/trending`, { signal: controller.signal })
      .then((response) => {
        setTrendingState({
          status: "success",
          movies: response.data.results || [],
        });
      })
      .catch((requestError) => {
        if (requestError.code !== "ERR_CANCELED") {
          setTrendingState({ status: "error", movies: [] });
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    axios
      .get(`${API_BASE_URL}/genres`, { signal: controller.signal })
      .then((response) => {
        const genres = Array.isArray(response.data.genres)
          ? response.data.genres.filter(
              (genre) => typeof genre === "string" && genre.trim(),
            )
          : [];

        setGenreState({
          status: "success",
          genres: genres.length > 0 ? genres : DEFAULT_GENRES,
        });
      })
      .catch((requestError) => {
        if (requestError.code !== "ERR_CANCELED") {
          setGenreState({ status: "error", genres: DEFAULT_GENRES });
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!isSuggestionsOpen || !searchQuery) return undefined;

    const controller = new AbortController();
    const debounceTimer = window.setTimeout(() => {
      axios
        .get(`${API_BASE_URL}/search`, {
          params: { query: searchQuery },
          signal: controller.signal,
        })
        .then((response) => {
          setSearchResponse({
            query: searchQuery,
            results: response.data.results || [],
            error: false,
          });
        })
        .catch((requestError) => {
          if (requestError.code !== "ERR_CANCELED") {
            setSearchResponse({
              query: searchQuery,
              results: [],
              error: true,
            });
          }
        });
    }, 300);

    return () => {
      window.clearTimeout(debounceTimer);
      controller.abort();
    };
  }, [isSuggestionsOpen, searchQuery]);

  useEffect(() => {
    if (
      !shouldScrollToRecommendations.current ||
      recommendations.length === 0
    ) {
      return;
    }

    shouldScrollToRecommendations.current = false;
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    recommendationsRef.current?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
      block: "start",
    });
  }, [recommendations]);

  const selectSuggestion = (movieTitle) => {
    setSearchTerm(movieTitle);
    setSelectedMovie(movieTitle);
    setIsSuggestionsOpen(false);
    setActiveSuggestion(-1);
  };

  const handleSearchChange = (event) => {
    const value = event.target.value;
    setSearchTerm(value);
    setSelectedMovie(value);
    setIsSuggestionsOpen(Boolean(value.trim()));
    setActiveSuggestion(-1);
  };

  const handleSearchKeyDown = (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsSuggestionsOpen(Boolean(searchQuery));
      if (suggestions.length > 0) {
        setActiveSuggestion((current) =>
          Math.min(current + 1, suggestions.length - 1),
        );
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (suggestions.length > 0) {
        setActiveSuggestion((current) =>
          current <= 0 ? suggestions.length - 1 : current - 1,
        );
      }
    } else if (event.key === "Enter" && activeSuggestion >= 0) {
      event.preventDefault();
      selectSuggestion(suggestions[activeSuggestion]);
    } else if (event.key === "Escape") {
      setIsSuggestionsOpen(false);
      setActiveSuggestion(-1);
    }
  };

  const selectGenre = (genre) => {
    if (genre === selectedGenre) return;

    setSelectedGenre(genre);
    setRecommendations([]);
    setError("");
  };

  const restoreHistoryItem = (item) => {
    setSearchTerm(item.searchedMovie);
    setSelectedMovie(item.searchedMovie);
    setSelectedGenre(item.selectedGenre);
    setRecommendationContext({
      movieTitle: item.searchedMovie,
      genre: item.selectedGenre,
    });
    setError("");
    setIsSuggestionsOpen(false);
    setActiveSuggestion(-1);
    shouldScrollToRecommendations.current = true;
    setRecommendations([...item.recommendations]);
  };

  const getRecommendations = async (event) => {
    event.preventDefault();

    const movieTitle = selectedMovie.trim();
    if (!movieTitle) return;

    setIsRecommending(true);
    setError("");
    setIsSuggestionsOpen(false);

    try {
      const res = await axios.get(
        `${API_BASE_URL}/recommend/${encodeURIComponent(movieTitle)}`,
        { params: { genre: selectedGenre } },
      );

      if (res.data.error) {
        setRecommendations([]);
        setError(res.data.error);
        return;
      }

      const receivedRecommendations = res.data.recommendations || [];
      setRecommendationContext({ movieTitle, genre: selectedGenre });

      if (receivedRecommendations.length > 0) {
        activity.addRecommendationHistory({
          searchedMovie: movieTitle,
          selectedGenre,
          recommendations: receivedRecommendations,
        });
        shouldScrollToRecommendations.current = true;
        setRecommendations(receivedRecommendations);
      } else {
        setRecommendations([]);
        setError(
          `No ${selectedGenre === "All" ? "" : `${selectedGenre} `}recommendations found for ${movieTitle}. Try another genre.`,
        );
      }
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setRecommendations([]);
      setError(
        typeof detail === "string"
          ? detail
          : "Something interrupted the search. Please give it another try.",
      );
    } finally {
      setIsRecommending(false);
    }
  };

  return (
    <main className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel">
        <SiteNav
          favoritesCount={collections.favorites.length}
          watchlistCount={collections.watchlist.length}
        />
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
          <label htmlFor="movie-search-input">Start with a movie</label>
          <div className="search-controls">
            <div
              className="autocomplete"
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) {
                  setIsSuggestionsOpen(false);
                  setActiveSuggestion(-1);
                }
              }}
            >
              <div className="search-input-wrap">
                <SearchIcon />
                <input
                  id="movie-search-input"
                  className="search-input"
                  type="search"
                  value={searchTerm}
                  placeholder="Search for a movie…"
                  autoComplete="off"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={isSuggestionsOpen}
                  aria-controls="movie-suggestions"
                  aria-activedescendant={
                    activeSuggestion >= 0
                      ? `movie-suggestion-${activeSuggestion}`
                      : undefined
                  }
                  onChange={handleSearchChange}
                  onFocus={() =>
                    setIsSuggestionsOpen(Boolean(searchQuery))
                  }
                  onKeyDown={handleSearchKeyDown}
                />
                {isSearching && (
                  <span className="search-spinner" aria-label="Searching" />
                )}
              </div>

              {isSuggestionsOpen && searchQuery && (
                <div
                  className="suggestions-dropdown"
                  id="movie-suggestions"
                  role="listbox"
                  aria-label="Movie suggestions"
                >
                  {isSearching ? (
                    <div className="suggestion-message">
                      <span className="search-spinner" aria-hidden="true" />
                      Searching movies…
                    </div>
                  ) : searchResponse.error ? (
                    <div className="suggestion-message suggestion-error">
                      Search is unavailable. Please try again.
                    </div>
                  ) : suggestions.length > 0 ? (
                    suggestions.map((movie, index) => (
                      <button
                        id={`movie-suggestion-${index}`}
                        className={`suggestion-item ${
                          activeSuggestion === index ? "is-active" : ""
                        }`}
                        type="button"
                        role="option"
                        aria-selected={activeSuggestion === index}
                        key={movie}
                        onMouseEnter={() => setActiveSuggestion(index)}
                        onClick={() => selectSuggestion(movie)}
                      >
                        <span className="suggestion-icon">
                          <FilmIcon />
                        </span>
                        <span>{movie}</span>
                      </button>
                    ))
                  ) : (
                    <div className="suggestion-message">No movies found</div>
                  )}
                </div>
              )}
            </div>

            <button
              className="recommend-button"
              type="submit"
              disabled={!selectedMovie.trim() || isRecommending}
            >
              {isRecommending ? (
                <span className="spinner" aria-hidden="true" />
              ) : (
                <SparkleIcon />
              )}
              {isRecommending ? "Finding matches…" : "Recommend"}
            </button>
          </div>

          <fieldset
            className="genre-filter"
            aria-busy={genreState.status === "loading"}
          >
            <legend>Filter recommendations by genre</legend>
            <div className="genre-chips">
              {genreState.genres.map((genre) => (
                <button
                  className={`genre-chip ${
                    selectedGenre === genre ? "is-active" : ""
                  }`}
                  type="button"
                  aria-pressed={selectedGenre === genre}
                  key={genre}
                  onClick={() => selectGenre(genre)}
                >
                  {genre}
                </button>
              ))}
            </div>
            {genreState.status === "error" && (
              <p className="genre-status">
                Using the standard genre collection.
              </p>
            )}
          </fieldset>
        </form>

        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}

        {recommendations.length > 0 && (
          <section
            className="results recommendations-section"
            ref={recommendationsRef}
            aria-live="polite"
          >
            <div className="results-heading">
              <div>
                <p className="section-kicker">Made for you</p>
                <h2>
                  Recommended for{" "}
                  <span className="recommendation-title">
                    {recommendationContext.movieTitle}
                  </span>
                </h2>
                <p className="section-subtitle">
                  Based on your selected movie and genre filter
                </p>
              </div>
              <span className="result-count">
                {recommendations.length}{" "}
                {recommendationContext.genre === "All"
                  ? "movies"
                  : `${recommendationContext.genre} matches`}
              </span>
            </div>

            <div className="movie-grid">
              {recommendations.map((movie, index) => (
                <MovieCard
                  movie={movie}
                  collections={collections}
                  showRecommendationInfo
                  key={`${movie.id || movie.title}-${index}`}
                />
              ))}
            </div>
          </section>
        )}

        <section
          className="results trending-section"
          aria-live="polite"
          aria-busy={trendingState.status === "loading"}
        >
          <div className="results-heading">
            <div>
              <p className="section-kicker">Popular on TMDB</p>
              <h2>Trending Today</h2>
            </div>
            {trendingState.status === "success" &&
              trendingState.movies.length > 0 && (
                <span className="result-count">Updated daily</span>
              )}
          </div>

          {trendingState.status === "loading" ? (
            <div className="movie-grid trending-grid">
              {Array.from({ length: 8 }, (_, index) => (
                <MovieCardSkeleton key={index} />
              ))}
            </div>
          ) : trendingState.status === "error" ? (
            <div className="trending-error" role="alert">
              <div className="trending-error-icon">
                <FilmIcon />
              </div>
              <div>
                <h3>Trending movies are taking a break</h3>
                <p>Please refresh the page in a moment.</p>
              </div>
            </div>
          ) : trendingState.movies.length > 0 ? (
            <div className="movie-grid trending-grid">
              {trendingState.movies.map((movie, index) => (
                <MovieCard
                  movie={movie}
                  collections={collections}
                  key={`${movie.id}-${index}`}
                />
              ))}
            </div>
          ) : (
            <div className="trending-error">
              No trending movies are available right now.
            </div>
          )}
        </section>

        {activity.recentlyViewed.length > 0 && (
          <section className="results recently-viewed-section">
            <div className="results-heading">
              <div>
                <p className="section-kicker">Pick up where you left off</p>
                <h2>Recently Viewed</h2>
              </div>
              <span className="result-count">
                {activity.recentlyViewed.length} recent
              </span>
            </div>

            <div className="movie-grid recently-viewed-grid">
              {activity.recentlyViewed.map((movie) => (
                <MovieCard
                  movie={movie}
                  collections={collections}
                  key={movie.id}
                />
              ))}
            </div>
          </section>
        )}

        <section className="results history-section">
          <div className="results-heading history-heading">
            <div>
              <p className="section-kicker">Return to an earlier search</p>
              <h2>Recommendation History</h2>
            </div>
            {activity.recommendationHistory.length > 0 && (
              <button
                className="clear-history-button"
                type="button"
                onClick={activity.clearRecommendationHistory}
              >
                <TrashIcon /> Clear all history
              </button>
            )}
          </div>

          {activity.recommendationHistory.length > 0 ? (
            <div className="history-grid">
              {activity.recommendationHistory.map((item) => (
                <article
                  className="history-card"
                  key={`${item.searchedMovie}-${item.selectedGenre}`}
                >
                  <button
                    className="history-restore-button"
                    type="button"
                    onClick={() => restoreHistoryItem(item)}
                  >
                    <div className="history-card-topline">
                      <span className="history-icon">
                        <SparkleIcon />
                      </span>
                      <time dateTime={new Date(item.createdAt).toISOString()}>
                        {formatRelativeTime(item.createdAt)}
                      </time>
                    </div>
                    <h3>{item.searchedMovie}</h3>
                    <div className="history-meta">
                      <span>{item.selectedGenre}</span>
                      <span>
                        {item.recommendations.length}{" "}
                        {item.recommendations.length === 1
                          ? "recommendation"
                          : "recommendations"}
                      </span>
                    </div>
                    <span className="history-restore-label">
                      Restore recommendations →
                    </span>
                  </button>
                  <button
                    className="history-delete-button"
                    type="button"
                    aria-label={`Delete history for ${item.searchedMovie}`}
                    title="Delete history item"
                    onClick={() =>
                      activity.removeHistoryItem(
                        item.searchedMovie,
                        item.selectedGenre,
                      )
                    }
                  >
                    <TrashIcon />
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <div className="history-empty">
              <SparkleIcon />
              <div>
                <h3>No recommendation history yet</h3>
                <p>Your successful movie searches will appear here.</p>
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

function SavedMoviesPage({ collection, collections }) {
  const isFavoritesPage = collection === "favorites";
  const movies = isFavoritesPage
    ? collections.favorites
    : collections.watchlist;
  const title = isFavoritesPage ? "Your Favorites" : "Your Watchlist";
  const subtitle = isFavoritesPage
    ? "The movies you loved, all in one place."
    : "A hand-picked queue for your next movie night.";
  const emptyTitle = isFavoritesPage
    ? "No favorites yet"
    : "Your watchlist is empty";
  const emptyMessage = isFavoritesPage
    ? "Tap the heart on any movie card to save it here."
    : "Tap the bookmark on a movie card to build your watchlist.";
  const removeMovie = isFavoritesPage
    ? collections.removeFavorite
    : collections.removeFromWatchlist;

  return (
    <main className="app-shell collection-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel collection-panel">
        <SiteNav
          favoritesCount={collections.favorites.length}
          watchlistCount={collections.watchlist.length}
        />

        <header className="collection-hero">
          <p className="section-kicker">Your personal cinema</p>
          <h1>{title}</h1>
          <p>{subtitle}</p>
          {movies.length > 0 && (
            <span className="collection-count">
              {movies.length} {movies.length === 1 ? "movie" : "movies"}
            </span>
          )}
        </header>

        {movies.length > 0 ? (
          <div className="movie-grid collection-grid">
            {movies.map((movie) => (
              <MovieCard
                movie={movie}
                collections={collections}
                onRemove={removeMovie}
                removeLabel={
                  isFavoritesPage
                    ? "Remove from Favorites"
                    : "Remove from Watchlist"
                }
                key={movie.id}
              />
            ))}
          </div>
        ) : (
          <div className="collection-empty">
            <div className="collection-empty-icon">
              {isFavoritesPage ? <HeartIcon /> : <BookmarkIcon />}
            </div>
            <h2>{emptyTitle}</h2>
            <p>{emptyMessage}</p>
            <Link className="collection-home-button" to="/">
              Discover movies
            </Link>
          </div>
        )}
      </section>

      <footer>
        <FilmIcon />
        <span>Thoughtful picks, one movie at a time.</span>
      </footer>
    </main>
  );
}

function App() {
  const activity = useMovieActivity();
  const collections = useMovieCollections();

  return (
    <Routes>
      <Route
        path="/"
        element={<Home activity={activity} collections={collections} />}
      />
      <Route
        path="/favorites"
        element={
          <SavedMoviesPage collection="favorites" collections={collections} />
        }
      />
      <Route
        path="/watchlist"
        element={
          <SavedMoviesPage collection="watchlist" collections={collections} />
        }
      />
      <Route
        path="/dashboard"
        element={
          <Dashboard
            activity={activity}
            collections={collections}
            navigation={
              <SiteNav
                favoritesCount={collections.favorites.length}
                watchlistCount={collections.watchlist.length}
              />
            }
          />
        }
      />
      <Route
        path="/movie/:id"
        element={<MovieDetails onMovieViewed={activity.addRecentlyViewed} />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
