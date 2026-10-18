import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import TVCard from "./TVCard";
import { getTrendingTVSeries, getTVRecommendations, searchTVSeries } from "./tvApi";
import "./TVDiscovery.css";

function FilmIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6.5h16v11H4zM8 6.5v11M16 6.5v11M4 10h4m8 0h4M4 14h4m8 0h4M7 3.5l2 3m3-3 2 3m3-3 2 3" />
    </svg>
  );
}

function TvIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
      <polyline points="17 2 12 7 7 2" />
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

function FlameIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 17c1.38 0 2.5-1.12 2.5-2.5 0-1.63-1.04-2.88-2.02-4.06-.5-.6-.98-1.2-1.33-1.84A6.74 6.74 0 0 0 9 12a3.8 3.8 0 0 0-.5 2.5Z" />
      <path d="M12 2c1 3 4 4.5 4 8.5a6 6 0 1 1-12 0c0-2.88 1.54-5.3 3.5-6.85.5 1.5 1.5 2.85 2.5 3.35C10.5 5 11 3 12 2Z" />
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

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6" />
    </svg>
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

function LoadMoreButton({
  visibleCount,
  totalCount,
  onLoadMore,
  step = 5,
  label = "Load More",
}) {
  const remaining = totalCount - visibleCount;
  if (remaining <= 0) return null;

  return (
    <div className="load-more-wrap">
      <button className="load-more-button" type="button" onClick={onLoadMore}>
        {label}
        <span>
          Show {Math.min(step, remaining)} of {remaining} more
        </span>
      </button>
    </div>
  );
}

const AVAILABLE_GENRES = [
  "All",
  "Action",
  "Drama",
  "Comedy",
  "Sci-Fi",
  "Crime",
  "Mystery",
  "Animation",
];

const INITIAL_VISIBLE_TRENDING = 6;
const TRENDING_LOAD_STEP = 4;
const INITIAL_VISIBLE_RECENT = 5;
const RECENT_LOAD_STEP = 5;
const INITIAL_VISIBLE_HISTORY = 6;
const HISTORY_LOAD_STEP = 6;

export default function TVDiscovery({ activity, collections, navigation }) {
  // -------------------------------------------------------------
  // 1. Hero Search & Autocomplete State
  // -------------------------------------------------------------
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [selectedSeries, setSelectedSeries] = useState(null);
  const [selectedGenre, setSelectedGenre] = useState("All");
  const [isSuggestionsOpen, setIsSuggestionsOpen] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [topError, setTopError] = useState("");
  const [suggestionsResponse, setSuggestionsResponse] = useState({
    query: "",
    results: [],
    error: false,
  });

  // -------------------------------------------------------------
  // 2. Recommendations State
  // -------------------------------------------------------------
  const [isRecommending, setIsRecommending] = useState(false);
  const [recommendationsState, setRecommendationsState] = useState({
    series: null,
    items: [],
    error: "",
  });
  const recommendationsRef = useRef(null);

  // -------------------------------------------------------------
  // 3. Trending State (TMDB)
  // -------------------------------------------------------------
  const [trendingState, setTrendingState] = useState({
    loaded: false,
    series: [],
    error: "",
  });

  const [visibleTrendingCount, setVisibleTrendingCount] = useState(INITIAL_VISIBLE_TRENDING);
  const [visibleRecentCount, setVisibleRecentCount] = useState(INITIAL_VISIBLE_RECENT);
  const [visibleHistoryCount, setVisibleHistoryCount] = useState(INITIAL_VISIBLE_HISTORY);
  const activeTVRecommendationRequest = useRef(null);

  useEffect(() => {
    return () => {
      activeTVRecommendationRequest.current?.abort();
    };
  }, []);

  // Debounce Hero Search Input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchTerm.trim());
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Fetch Hero Search Suggestions
  useEffect(() => {
    if (!debouncedSearchQuery) {
      return;
    }

    const controller = new AbortController();

    searchTVSeries(debouncedSearchQuery, { signal: controller.signal })
      .then((data) => {
        setSuggestionsResponse({
          query: debouncedSearchQuery,
          results: data.results || [],
          error: false,
        });
      })
      .catch((err) => {
        if (err.name !== "CanceledError" && err.code !== "ERR_CANCELED") {
          setSuggestionsResponse({
            query: debouncedSearchQuery,
            results: [],
            error: true,
          });
        }
      });

    return () => controller.abort();
  }, [debouncedSearchQuery]);

  // Fetch Trending Series from TMDB
  useEffect(() => {
    const controller = new AbortController();

    getTrendingTVSeries({ signal: controller.signal })
      .then((data) => {
        setTrendingState({
          loaded: true,
          series: data.results || [],
          error: "",
        });
      })
      .catch((err) => {
        if (err.name !== "CanceledError" && err.code !== "ERR_CANCELED") {
          setTrendingState({
            loaded: true,
            series: [],
            error: "Unable to load trending TV series from TMDB.",
          });
        }
      });

    return () => controller.abort();
  }, []);

  // Handlers for Autocomplete & Selection
  const searchQueryTrimmed = searchTerm.trim();
  const hasCurrentSuggestions = suggestionsResponse.query === searchQueryTrimmed;
  const suggestions = hasCurrentSuggestions ? suggestionsResponse.results : [];
  const isSearchingSuggestions =
    isSuggestionsOpen && Boolean(searchQueryTrimmed) && !hasCurrentSuggestions;

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchTerm(value);

    if (!value.trim()) {
      setSelectedSeries(null);
      setRecommendationsState({ series: null, items: [], error: "" });
      setIsRecommending(false);
      setTopError("");
      setIsSuggestionsOpen(false);
      setActiveSuggestion(-1);
      if (activeTVRecommendationRequest.current) {
        activeTVRecommendationRequest.current.abort();
        activeTVRecommendationRequest.current = null;
      }
    } else {
      setSelectedSeries(null);
      setTopError("");
      setActiveSuggestion(-1);
      setIsSuggestionsOpen(true);
    }
  };

  const selectSuggestion = (series) => {
    setSelectedSeries(series);
    setSearchTerm(series.name);
    setTopError("");
    setIsSuggestionsOpen(false);
    setActiveSuggestion(-1);
  };

  // Recommend Trigger Logic
  const triggerRecommendations = useCallback(
    (seriesToRecommend, genreOverride) => {
      if (!seriesToRecommend || seriesToRecommend.id == null) return;

      activeTVRecommendationRequest.current?.abort();
      const controller = new AbortController();
      activeTVRecommendationRequest.current = controller;

      const genreToUse = genreOverride !== undefined ? genreOverride : selectedGenre;
      setIsRecommending(true);
      setTopError("");
      setRecommendationsState({
        series: seriesToRecommend,
        items: [],
        error: "",
      });

      getTVRecommendations(seriesToRecommend.id, { limit: 12, signal: controller.signal })
        .then((data) => {
          if (activeTVRecommendationRequest.current !== controller) return;

          const receivedRecommendations = data.recommendations || [];
          setRecommendationsState({
            series: seriesToRecommend,
            items: receivedRecommendations,
            error: "",
          });
          setIsRecommending(false);
          activeTVRecommendationRequest.current = null;

          if (receivedRecommendations.length > 0 && activity?.addRecommendationHistory) {
            activity.addRecommendationHistory({
              searchedMovie: seriesToRecommend.name || seriesToRecommend.title,
              selectedGenre: genreToUse,
              recommendations: receivedRecommendations,
              media_type: "tv",
            });
          }

          setTimeout(() => {
            recommendationsRef.current?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }, 100);
        })
        .catch((err) => {
          if (err.name === "CanceledError" || err.code === "ERR_CANCELED" || controller.signal.aborted) {
            return;
          }
          if (activeTVRecommendationRequest.current !== controller) return;

          setIsRecommending(false);
          activeTVRecommendationRequest.current = null;
          const detail = err.response?.data?.detail;
          setRecommendationsState({
            series: seriesToRecommend,
            items: [],
            error:
              typeof detail === "string"
                ? detail
                : "Unable to find recommendations for this series at this time.",
          });
        });
    },
    [activity, selectedGenre],
  );

  const handleRecommendSubmit = async (e) => {
    e.preventDefault();
    const query = searchTerm.trim();
    if (!query) {
      setSelectedSeries(null);
      setRecommendationsState({ series: null, items: [], error: "" });
      setIsRecommending(false);
      setTopError("");
      return;
    }

    setIsSuggestionsOpen(false);
    setActiveSuggestion(-1);
    setTopError("");

    let targetSeries = selectedSeries;
    // If selectedSeries is not set or name differs from query, find matching series
    if (!targetSeries || targetSeries.name.trim().toLowerCase() !== query.toLowerCase()) {
      setIsRecommending(true);
      try {
        const searchRes = await searchTVSeries(query);
        const results = searchRes.results || [];
        if (results.length === 0) {
          setIsRecommending(false);
          setTopError(`No TV series found matching “${query}”. Please try a different title.`);
          return;
        }
        // Exact match first, or fallback to first result
        const exactMatch = results.find(
          (s) => s.name.trim().toLowerCase() === query.toLowerCase(),
        );
        targetSeries = exactMatch || results[0];
        setSelectedSeries(targetSeries);
        setSearchTerm(targetSeries.name);
      } catch {
        setIsRecommending(false);
        setTopError("Unable to search TV series at this time. Please try again.");
        return;
      }
    }

    if (!targetSeries || targetSeries.id == null) {
      setIsRecommending(false);
      setTopError("Unable to find series ID for recommendation.");
      return;
    }

    triggerRecommendations(targetSeries);
  };

  const handleSearchKeyDown = (e) => {
    if (!isSuggestionsOpen || suggestions.length === 0) {
      if (e.key === "Enter") {
        e.preventDefault();
        handleRecommendSubmit(e);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestion((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestion((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeSuggestion >= 0 && activeSuggestion < suggestions.length) {
        selectSuggestion(suggestions[activeSuggestion]);
      } else {
        handleRecommendSubmit(e);
      }
    } else if (e.key === "Escape") {
      setIsSuggestionsOpen(false);
      setActiveSuggestion(-1);
    }
  };

  const selectGenre = (genre) => {
    setSelectedGenre(genre);
  };

  // Restore TV Recommendation History Item
  const restoreHistoryItem = (item) => {
    const seriesTitle = item.searchedMovie;
    setSearchTerm(seriesTitle);
    setSelectedSeries({
      name: seriesTitle,
      title: seriesTitle,
    });
    setSelectedGenre(item.selectedGenre || "All");
    setTopError("");
    setIsSuggestionsOpen(false);
    setActiveSuggestion(-1);

    setRecommendationsState({
      series: { name: seriesTitle, title: seriesTitle },
      items: item.recommendations || [],
      error: "",
    });

    setTimeout(() => {
      recommendationsRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 100);
  };

  // -------------------------------------------------------------
  // Data Slicing for Recently Viewed & History (strictly TV items)
  // -------------------------------------------------------------
  const tvRecentlyViewed = useMemo(() => {
    const items = activity?.recentlyViewed || [];
    return items.filter((item) => item.media_type === "tv");
  }, [activity?.recentlyViewed]);

  const displayedRecentlyViewed = tvRecentlyViewed.slice(0, visibleRecentCount);

  const tvRecommendationHistory = useMemo(() => {
    const items = activity?.recommendationHistory || [];
    return items.filter((item) => item.media_type === "tv");
  }, [activity?.recommendationHistory]);

  const displayedHistoryItems = tvRecommendationHistory.slice(0, visibleHistoryCount);

  // Recommendations filtered by active genre
  const displayedRecommendations = useMemo(() => {
    if (!recommendationsState.items || recommendationsState.items.length === 0) {
      return [];
    }
    if (selectedGenre === "All") {
      return recommendationsState.items;
    }
    return recommendationsState.items.filter((item) => {
      const g = Array.isArray(item.genres)
        ? item.genres.join(" ")
        : typeof item.genres === "string"
        ? item.genres
        : "";
      return g.toLowerCase().includes(selectedGenre.toLowerCase());
    });
  }, [recommendationsState.items, selectedGenre]);

  return (
    <main className="app-shell tv-discovery-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel tv-discovery-panel">
        {navigation}

        {/* Media Switcher: Movies / TV Series */}
        <div className="media-switcher-wrapper">
          <nav className="media-switcher" aria-label="Media format selector">
            <Link className="media-switch-pill" to="/">
              <FilmIcon />
              <span>Movies</span>
            </Link>
            <div className="media-switch-pill is-active" aria-current="page">
              <TvIcon />
              <span>TV Series</span>
            </div>
          </nav>
        </div>

        {/* Hero Section */}
        <header className="hero-copy">
          <div className="brand-mark" aria-hidden="true">
            <TvIcon />
          </div>
          <p className="eyebrow">
            <span /> YOUR NEXT BINGE STARTS HERE
          </p>
          <h1>
            Discover Your Next <span>Favourite Series.</span>
          </h1>
          <p className="hero-description">
            Choose a series you already enjoy and discover your next binge-worthy obsession in seconds.
          </p>
        </header>

        {/* Primary TV Recommendation Search Form */}
        <form className="movie-search tv-hero-search" onSubmit={handleRecommendSubmit}>
          <label htmlFor="tv-search-input">Start with a TV series</label>
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
                  id="tv-search-input"
                  className="search-input"
                  type="search"
                  value={searchTerm}
                  placeholder="Search for a TV series (e.g. Weak Hero, NCIS)…"
                  autoComplete="off"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={isSuggestionsOpen}
                  aria-controls="tv-suggestions"
                  aria-activedescendant={
                    activeSuggestion >= 0
                      ? `tv-suggestion-${activeSuggestion}`
                      : undefined
                  }
                  onChange={handleSearchChange}
                  onInput={(e) => {
                    if (!e.target.value.trim()) {
                      handleSearchChange(e);
                    }
                  }}
                  onSearch={(e) => {
                    if (!e.target.value.trim()) {
                      handleSearchChange(e);
                    }
                  }}
                  onFocus={() => {
                    if (searchQueryTrimmed) setIsSuggestionsOpen(true);
                  }}
                  onKeyDown={handleSearchKeyDown}
                />
                {isSearchingSuggestions && (
                  <span className="search-spinner" aria-label="Searching suggestions" />
                )}
              </div>

              {isSuggestionsOpen && searchQueryTrimmed && (
                <div
                  className="suggestions-dropdown"
                  id="tv-suggestions"
                  role="listbox"
                  aria-label="TV series suggestions"
                >
                  {isSearchingSuggestions ? (
                    <div className="suggestion-message">
                      <span className="search-spinner" aria-hidden="true" />
                      Searching TV series…
                    </div>
                  ) : suggestionsResponse.error ? (
                    <div className="suggestion-message suggestion-error">
                      Search is unavailable. Please try again.
                    </div>
                  ) : suggestions.length > 0 ? (
                    suggestions.map((series, index) => {
                      const year = series.first_air_date ? series.first_air_date.slice(0, 4) : "";
                      const rating =
                        typeof series.vote_average === "number" && series.vote_average > 0
                          ? `★ ${series.vote_average.toFixed(1)}`
                          : "";

                      return (
                        <button
                          id={`tv-suggestion-${index}`}
                          className={`suggestion-item tv-suggestion-item ${
                            activeSuggestion === index ? "is-active" : ""
                          }`}
                          type="button"
                          role="option"
                          aria-selected={activeSuggestion === index}
                          key={series.id}
                          onMouseEnter={() => setActiveSuggestion(index)}
                          onClick={() => selectSuggestion(series)}
                        >
                          <div className="suggestion-thumbnail">
                            {series.poster_url ? (
                              <img src={series.poster_url} alt="" />
                            ) : (
                              <TvIcon />
                            )}
                          </div>
                          <div className="suggestion-info">
                            <span className="suggestion-title">{series.name}</span>
                            <span className="suggestion-meta">
                              {year}
                              {year && rating ? " · " : ""}
                              {rating}
                              {series.number_of_seasons ? ` · ${series.number_of_seasons} Seasons` : ""}
                            </span>
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="suggestion-message">
                      No series found matching &ldquo;{searchQueryTrimmed}&rdquo;
                    </div>
                  )}
                </div>
              )}
            </div>

            <button
              className="recommend-button"
              type="submit"
              disabled={!searchTerm.trim() || isRecommending}
            >
              {isRecommending ? (
                <span className="spinner" aria-hidden="true" />
              ) : (
                <SparkleIcon />
              )}
              {isRecommending ? "Finding matches…" : "Recommend"}
            </button>
          </div>

          {/* Genre Filter Chips directly below the primary search input */}
          <fieldset className="genre-filter">
            <legend>Filter recommendations by genre</legend>
            <div className="genre-chips">
              {AVAILABLE_GENRES.map((genre) => (
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
          </fieldset>
        </form>

        {topError && (
          <p className="error-message" role="alert">
            {topError}
          </p>
        )}

        {/* ----------------------------------------------------------- */}
        {/* Recommended For You Section                                  */}
        {/* ----------------------------------------------------------- */}
        {isRecommending && (
          <section
            className="results recommendations-section"
            ref={recommendationsRef}
            aria-live="polite"
            aria-busy="true"
          >
            <div className="results-heading">
              <div>
                <p className="section-kicker">AI Semantic Engine</p>
                <h2>
                  Finding matches for{" "}
                  <span className="recommendation-title">
                    {recommendationsState.series?.name || searchTerm}
                  </span>
                </h2>
                <p className="section-subtitle">
                  Analyzing semantic storyline embeddings, tone, and character dynamics…
                </p>
              </div>
              <span className="result-count">Loading</span>
            </div>

            <div className="movie-grid">
              {Array.from({ length: 4 }).map((_, index) => (
                <article className="movie-card movie-card-skeleton" key={index}>
                  <div className="poster-art skeleton-shimmer" />
                  <div className="movie-details">
                    <span className="details-skeleton-title skeleton-shimmer" />
                    <span className="details-skeleton-pill skeleton-shimmer" />
                    <span className="details-skeleton-copy-line skeleton-shimmer" />
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {!isRecommending && recommendationsState.error && (
          <section
            className="results recommendations-section"
            ref={recommendationsRef}
            aria-live="polite"
          >
            <div className="tv-error-box" role="alert">
              <p>{recommendationsState.error}</p>
              {recommendationsState.series && (
                <button
                  type="button"
                  className="details-button details-button-secondary"
                  onClick={() => triggerRecommendations(recommendationsState.series)}
                >
                  Retry Recommendations
                </button>
              )}
            </div>
          </section>
        )}

        {!isRecommending && recommendationsState.items.length > 0 && (
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
                    {recommendationsState.series?.name || searchTerm}
                  </span>
                </h2>
                <p className="section-subtitle">
                  AI-ranked by semantic story overview and thematic similarity
                </p>
              </div>
              <div className="recommendations-heading-actions">
                <span className="result-count">
                  {displayedRecommendations.length}{" "}
                  {displayedRecommendations.length === 1 ? "series match" : "series matches"}
                </span>
                <button
                  type="button"
                  className="clear-recommendations-btn"
                  onClick={() =>
                    setRecommendationsState({ series: null, items: [], error: "" })
                  }
                >
                  Clear picks
                </button>
              </div>
            </div>

            {displayedRecommendations.length > 0 ? (
              <div className="movie-grid">
                {displayedRecommendations.map((series) => (
                  <TVCard
                    key={series.id}
                    series={series}
                    collections={collections}
                    showRecommendationInfo={true}
                  />
                ))}
              </div>
            ) : (
              <div className="collection-empty tv-empty-box">
                <h3>No &ldquo;{selectedGenre}&rdquo; recommendations found</h3>
                <p>
                  None of the recommendations for &ldquo;{recommendationsState.series?.name}&rdquo;
                  are categorized under &ldquo;{selectedGenre}&rdquo;.
                </p>
                <button
                  type="button"
                  className="genre-chip is-active"
                  onClick={() => setSelectedGenre("All")}
                >
                  Show All Genres ({recommendationsState.items.length})
                </button>
              </div>
            )}
          </section>
        )}

        {/* ----------------------------------------------------------- */}
        {/* Trending Section (TMDB)                                      */}
        {/* ----------------------------------------------------------- */}
        <section className="results trending-section" aria-label="Trending TV Series">
          <div className="results-heading trending-heading-row">
            <div>
              <p className="section-kicker">Popular on TMDB</p>
              <h2>
                <FlameIcon /> Trending This Week
              </h2>
            </div>
            {trendingState.loaded && !trendingState.error && (
              <span className="trending-badge">Live from TMDB</span>
            )}
          </div>

          {!trendingState.loaded && (
            <div className="movie-grid">
              {Array.from({ length: 6 }).map((_, index) => (
                <article className="movie-card movie-card-skeleton" key={index}>
                  <div className="poster-art skeleton-shimmer" />
                  <div className="movie-details">
                    <span className="details-skeleton-title skeleton-shimmer" />
                    <span className="details-skeleton-pill skeleton-shimmer" />
                    <span className="details-skeleton-copy-line skeleton-shimmer" />
                  </div>
                </article>
              ))}
            </div>
          )}

          {trendingState.loaded && trendingState.error && (
            <div className="tv-error-box" role="alert">
              <p>{trendingState.error}</p>
              <button
                type="button"
                className="details-button details-button-secondary"
                onClick={() => {
                  setTrendingState({ loaded: false, series: [], error: "" });
                  getTrendingTVSeries()
                    .then((data) =>
                      setTrendingState({
                        loaded: true,
                        series: data.results || [],
                        error: "",
                      }),
                    )
                    .catch(() =>
                      setTrendingState({
                        loaded: true,
                        series: [],
                        error: "Unable to load trending TV series from TMDB.",
                      }),
                    );
                }}
              >
                Retry
              </button>
            </div>
          )}

          {trendingState.loaded && !trendingState.error && (
            <>
              <div className="movie-grid trending-grid">
                {trendingState.series
                  .slice(0, visibleTrendingCount)
                  .map((series) => (
                    <TVCard
                      key={series.id}
                      series={series}
                      collections={collections}
                    />
                  ))}
              </div>

              <LoadMoreButton
                visibleCount={visibleTrendingCount}
                totalCount={trendingState.series.length}
                step={TRENDING_LOAD_STEP}
                label="Load More"
                onLoadMore={() =>
                  setVisibleTrendingCount((prev) =>
                    Math.min(prev + TRENDING_LOAD_STEP, trendingState.series.length),
                  )
                }
              />
            </>
          )}
        </section>

        {/* ----------------------------------------------------------- */}
        {/* Personalized Section A: Recently Viewed                      */}
        {/* ----------------------------------------------------------- */}
        <section className="results recently-viewed-section" aria-label="Recently Viewed TV Series">
          <div className="results-heading">
            <div>
              <p className="section-kicker">Pick up where you left off</p>
              <h2>Recently Viewed</h2>
            </div>
            {tvRecentlyViewed.length > 0 && (
              <span className="result-count">
                {tvRecentlyViewed.length} recent
              </span>
            )}
          </div>

          {tvRecentlyViewed.length > 0 ? (
            <>
              <div className="movie-grid recently-viewed-grid">
                {displayedRecentlyViewed.map((series) => (
                  <TVCard
                    key={series.id}
                    series={series}
                    collections={collections}
                  />
                ))}
              </div>

              <LoadMoreButton
                visibleCount={visibleRecentCount}
                totalCount={tvRecentlyViewed.length}
                step={RECENT_LOAD_STEP}
                onLoadMore={() =>
                  setVisibleRecentCount((prev) =>
                    Math.min(prev + RECENT_LOAD_STEP, tvRecentlyViewed.length),
                  )
                }
              />
            </>
          ) : (
            <div className="collection-empty tv-empty-box">
              <div className="collection-empty-icon">
                <TvIcon />
              </div>
              <h3>No TV series viewed yet</h3>
              <p>
                Series you explore will appear here so you can easily pick up where you left off.
              </p>
            </div>
          )}
        </section>

        {/* ----------------------------------------------------------- */}
        {/* Personalized Section B: Return to an Earlier Search         */}
        {/* ----------------------------------------------------------- */}
        <section className="results history-section" aria-label="TV Recommendation History">
          <div className="results-heading history-heading">
            <div>
              <p className="section-kicker">Return to an earlier search</p>
              <h2>Recommendation History</h2>
            </div>
            {tvRecommendationHistory.length > 0 && (
              <button
                className="clear-history-button"
                type="button"
                onClick={() => activity?.clearRecommendationHistory?.("tv")}
              >
                <TrashIcon /> Clear all history
              </button>
            )}
          </div>

          {tvRecommendationHistory.length > 0 ? (
            <>
              <div className="history-grid">
                {displayedHistoryItems.map((item) => (
                  <article
                    className="history-card"
                    key={`${item.searchedMovie}-${item.selectedGenre}-${item.createdAt}`}
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
                      onClick={() => activity?.removeHistoryItem?.(item)}
                    >
                      <TrashIcon />
                    </button>
                  </article>
                ))}
              </div>

              <LoadMoreButton
                visibleCount={visibleHistoryCount}
                totalCount={tvRecommendationHistory.length}
                step={HISTORY_LOAD_STEP}
                label="Load More History"
                onLoadMore={() =>
                  setVisibleHistoryCount((prev) =>
                    Math.min(prev + HISTORY_LOAD_STEP, tvRecommendationHistory.length),
                  )
                }
              />
            </>
          ) : (
            <div className="history-empty">
              <SparkleIcon />
              <div>
                <h3>No TV recommendation history yet</h3>
                <p>Your successful TV series searches will appear here.</p>
              </div>
            </div>
          )}
        </section>
      </section>

      <footer>
        <TvIcon />
        <span>Immersive television, curated by CineMatch.</span>
      </footer>
    </main>
  );
}
