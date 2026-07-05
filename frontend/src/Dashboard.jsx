import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./Dashboard.css";

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
      <path d="M6 3.5h12v17l-6-4-6 4v-17Z" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.5" />
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

function FilmIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6.5h16v11H4zM8 6.5v11M16 6.5v11M4 10h4m8 0h4M4 14h4m8 0h4" />
    </svg>
  );
}

function formatRelativeTime(timestamp) {
  const elapsed = Math.max(0, Date.now() - Number(timestamp || 0));
  const minutes = Math.floor(elapsed / 60000);
  const hours = Math.floor(elapsed / 3600000);
  const days = Math.floor(elapsed / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

function getTopRecommended(history) {
  const moviesById = new Map();

  history.forEach((entry) => {
    entry.recommendations.forEach((movie) => {
      const key = movie.id == null
        ? `title:${movie.title.toLocaleLowerCase()}`
        : `id:${movie.id}`;
      const score = Number.isFinite(Number(movie.match_score))
        ? Number(movie.match_score)
        : 0;
      const current = moviesById.get(key);

      if (!current || score > current.match_score) {
        moviesById.set(key, { ...movie, match_score: score });
      }
    });
  });

  return [...moviesById.values()]
    .sort((first, second) => second.match_score - first.match_score)
    .slice(0, 5);
}

function getSearchCounts(history) {
  const searches = new Map();

  history.forEach((entry) => {
    const key = entry.searchedMovie.trim().toLocaleLowerCase();
    const current = searches.get(key);
    searches.set(key, {
      title: current?.title || entry.searchedMovie,
      count: (current?.count || 0) + 1,
    });
  });

  return [...searches.values()]
    .sort((first, second) => second.count - first.count)
    .slice(0, 5);
}

function getGenreCounts(history) {
  const genres = new Map();

  history.forEach((entry) => {
    if (entry.selectedGenre.toLocaleLowerCase() === "all") return;

    const key = entry.selectedGenre.toLocaleLowerCase();
    const current = genres.get(key);
    genres.set(key, {
      genre: current?.genre || entry.selectedGenre,
      count: (current?.count || 0) + 1,
    });
  });

  return [...genres.values()]
    .sort((first, second) => second.count - first.count)
    .slice(0, 5);
}

function DashboardSkeleton({ navigation }) {
  return (
    <main className="app-shell dashboard-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel dashboard-panel">
        {navigation}

        <header className="dashboard-hero dashboard-hero-skeleton">
          <span className="dashboard-kicker-skeleton skeleton-shimmer" />
          <span className="dashboard-title-skeleton skeleton-shimmer" />
          <span className="dashboard-copy-skeleton skeleton-shimmer" />
        </header>

        <section className="dashboard-summary" aria-hidden="true">
          {Array.from({ length: 4 }, (_, index) => (
            <article className="summary-card summary-card-skeleton" key={index}>
              <span className="summary-icon skeleton-shimmer" />
              <span className="summary-number-skeleton skeleton-shimmer" />
              <span className="summary-label-skeleton skeleton-shimmer" />
              <span className="summary-action-skeleton skeleton-shimmer" />
            </article>
          ))}
        </section>

        <div className="dashboard-columns" aria-hidden="true">
          <section className="dashboard-section">
            <span className="dashboard-section-title-skeleton skeleton-shimmer" />
            <div className="dashboard-movie-list">
              {Array.from({ length: 5 }, (_, index) => (
                <span className="dashboard-row-skeleton skeleton-shimmer" key={index} />
              ))}
            </div>
          </section>
          <section className="dashboard-section">
            <span className="dashboard-section-title-skeleton skeleton-shimmer" />
            <div className="dashboard-movie-list">
              {Array.from({ length: 5 }, (_, index) => (
                <span className="dashboard-row-skeleton skeleton-shimmer" key={index} />
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function Dashboard({ activity, collections, navigation }) {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setIsReady(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  if (!isReady) {
    return <DashboardSkeleton navigation={navigation} />;
  }

  const topRecommended = getTopRecommended(activity.recommendationHistory);
  const mostSearched = getSearchCounts(activity.recommendationHistory);
  const favoriteGenres = getGenreCounts(activity.recommendationHistory);
  const maxGenreCount = Math.max(1, ...favoriteGenres.map((item) => item.count));
  const hasActivity =
    collections.favorites.length > 0 ||
    collections.watchlist.length > 0 ||
    activity.recentlyViewed.length > 0 ||
    activity.recommendationHistory.length > 0;

  const summaryCards = [
    {
      label: "Favorite Movies",
      count: collections.favorites.length,
      icon: <HeartIcon />,
      to: "/favorites",
      tone: "rose",
    },
    {
      label: "Watchlist Movies",
      count: collections.watchlist.length,
      icon: <BookmarkIcon />,
      to: "/watchlist",
      tone: "violet",
    },
    {
      label: "Recently Viewed",
      count: activity.recentlyViewed.length,
      icon: <EyeIcon />,
      href: "#latest-activity",
      tone: "blue",
    },
    {
      label: "Recommendation Searches",
      count: activity.recommendationHistory.length,
      icon: <SparkleIcon />,
      href: "#search-analytics",
      tone: "green",
    },
  ];

  return (
    <main className="app-shell dashboard-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel dashboard-panel">
        {navigation}

        <header className="dashboard-hero">
          <p className="section-kicker">Your viewing story</p>
          <h1>Activity Dashboard</h1>
          <p>A private, browser-only snapshot of your movie discoveries.</p>
        </header>

        <section className="dashboard-summary" aria-label="Activity summary">
          {summaryCards.map((card) => {
            const content = (
              <>
                <span className={`summary-icon ${card.tone}`}>{card.icon}</span>
                <strong>{card.count}</strong>
                <span className="summary-label">{card.label}</span>
                <span className="summary-action">View details →</span>
              </>
            );

            return card.to ? (
              <Link className="summary-card" to={card.to} key={card.label}>
                {content}
              </Link>
            ) : (
              <a className="summary-card" href={card.href} key={card.label}>
                {content}
              </a>
            );
          })}
        </section>

        {!hasActivity ? (
          <section className="dashboard-empty">
            <span><FilmIcon /></span>
            <h2>Your dashboard is ready</h2>
            <p>Start searching and saving movies to see your activity here.</p>
            <Link to="/">Discover movies</Link>
          </section>
        ) : (
          <>
            <div className="dashboard-columns">
              <section className="dashboard-section top-movies-section">
                <div className="dashboard-section-heading">
                  <div>
                    <p className="section-kicker">Your strongest matches</p>
                    <h2>Top Recommended Movies</h2>
                  </div>
                </div>

                {topRecommended.length > 0 ? (
                  <div className="dashboard-movie-list">
                    {topRecommended.map((movie, index) => {
                      const content = (
                        <>
                          <span className="dashboard-rank">{index + 1}</span>
                          <span className="dashboard-movie-poster">
                            {movie.poster_url ? (
                              <img src={movie.poster_url} alt="" />
                            ) : (
                              <FilmIcon />
                            )}
                          </span>
                          <span className="dashboard-movie-copy">
                            <strong>{movie.title}</strong>
                            <small>
                              {movie.release_date?.slice(0, 4) || "Year unavailable"}
                            </small>
                          </span>
                          <span className="dashboard-match">
                            {Math.round(movie.match_score)}% Match
                          </span>
                        </>
                      );

                      return movie.id ? (
                        <Link
                          className="dashboard-movie-row"
                          to={`/movie/${movie.id}`}
                          key={movie.id}
                        >
                          {content}
                        </Link>
                      ) : (
                        <div
                          className="dashboard-movie-row"
                          key={`title-${movie.title}`}
                        >
                          {content}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="dashboard-section-empty">
                    Complete a recommendation search to see your top matches.
                  </p>
                )}
              </section>

              <section className="dashboard-section" id="search-analytics">
                <div className="dashboard-section-heading">
                  <div>
                    <p className="section-kicker">Your repeat discoveries</p>
                    <h2>Most Searched Movies</h2>
                  </div>
                </div>

                {mostSearched.length > 0 ? (
                  <ol className="search-ranking">
                    {mostSearched.map((item, index) => (
                      <li key={item.title}>
                        <span>{index + 1}</span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.count} {item.count === 1 ? "search" : "searches"}
                        </small>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="dashboard-section-empty">
                    Your most searched movies will appear here.
                  </p>
                )}
              </section>
            </div>

            <section className="dashboard-section genre-analytics">
              <div className="dashboard-section-heading">
                <div>
                  <p className="section-kicker">Your taste profile</p>
                  <h2>Most Used Genres</h2>
                </div>
              </div>

              {favoriteGenres.length > 0 ? (
                <div className="genre-bars">
                  {favoriteGenres.map((item) => (
                    <div className="genre-bar-row" key={item.genre}>
                      <div>
                        <strong>{item.genre}</strong>
                        <span>{item.count}</span>
                      </div>
                      <span className="genre-bar-track">
                        <span
                          style={{ width: `${(item.count / maxGenreCount) * 100}%` }}
                        />
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="dashboard-section-empty">
                  Use a genre filter to begin building your taste profile.
                </p>
              )}
            </section>

            <section
              className="dashboard-section latest-activity-section"
              id="latest-activity"
            >
              <div className="dashboard-section-heading">
                <div>
                  <p className="section-kicker">What happened lately</p>
                  <h2>Latest Activity</h2>
                </div>
              </div>

              <div className="latest-activity-grid">
                <div className="latest-activity-column">
                  <h3>Recently viewed</h3>
                  {activity.recentlyViewed.length > 0 ? (
                    activity.recentlyViewed.slice(0, 5).map((movie) => (
                      <Link
                        className="recent-activity-item"
                        to={`/movie/${movie.id}`}
                        key={movie.id}
                      >
                        <span>
                          {movie.poster_url ? (
                            <img src={movie.poster_url} alt="" />
                          ) : (
                            <FilmIcon />
                          )}
                        </span>
                        <div>
                          <strong>{movie.title}</strong>
                          <small>Viewed recently</small>
                        </div>
                      </Link>
                    ))
                  ) : (
                    <p className="activity-column-empty">No movies viewed yet.</p>
                  )}
                </div>

                <div className="latest-activity-column">
                  <h3>Latest searches</h3>
                  {activity.recommendationHistory.length > 0 ? (
                    activity.recommendationHistory.slice(0, 5).map((item) => (
                      <div
                        className="search-activity-item"
                        key={`${item.searchedMovie}-${item.selectedGenre}`}
                      >
                        <span><SparkleIcon /></span>
                        <div>
                          <strong>{item.searchedMovie}</strong>
                          <small>
                            {item.selectedGenre} · {formatRelativeTime(item.createdAt)}
                          </small>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="activity-column-empty">No searches yet.</p>
                  )}
                </div>
              </div>
            </section>
          </>
        )}
      </section>

      <footer>
        <FilmIcon />
        <span>Your activity stays in this browser.</span>
      </footer>
    </main>
  );
}

export default Dashboard;
