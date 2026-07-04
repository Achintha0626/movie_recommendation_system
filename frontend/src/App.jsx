import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import MovieDetails from "./MovieDetails";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";
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

function Home() {
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
      .get(`${API_URL}/trending`, { signal: controller.signal })
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
      .get(`${API_URL}/genres`, { signal: controller.signal })
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
        .get(`${API_URL}/search`, {
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

  const getRecommendations = async (event) => {
    event.preventDefault();

    const movieTitle = selectedMovie.trim();
    if (!movieTitle) return;

    setIsRecommending(true);
    setError("");
    setIsSuggestionsOpen(false);

    try {
      const res = await axios.get(
        `${API_URL}/recommend/${encodeURIComponent(movieTitle)}`,
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
                <MovieCard movie={movie} key={`${movie.id}-${index}`} />
              ))}
            </div>
          ) : (
            <div className="trending-error">
              No trending movies are available right now.
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
