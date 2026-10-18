import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getTVDetails } from "./tvApi";
import "./TVDetails.css";

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

function TvIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2" y="7" width="20" height="15" rx="2" ry="2" fill="none" stroke="currentColor" strokeWidth="2" />
      <polyline points="17 2 12 7 7 2" fill="none" stroke="currentColor" strokeWidth="2" />
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

function TVDetailsSkeleton() {
  return (
    <main
      className="details-page details-skeleton-page"
      aria-busy="true"
      aria-label="Loading TV series details"
    >
      <section className="details-hero details-hero-skeleton">
        <div className="details-backdrop-shade" />

        <nav className="details-nav details-container" aria-label="TV navigation">
          <Link className="back-link" to="/tv">
            <ArrowLeftIcon /> Back to TV Series
          </Link>
          <div className="details-nav-right">
            <span className="details-nav-skeleton skeleton-shimmer" />
            <span className="details-nav-skeleton skeleton-shimmer" />
            <Link className="details-brand" to="/">
              <FilmIcon /> CineMatch
            </Link>
          </div>
        </nav>

        <div className="details-layout details-container">
          <div className="details-poster details-skeleton-poster skeleton-shimmer" />

          <div className="details-copy details-skeleton-copy">
            <span className="details-skeleton-kicker skeleton-shimmer" />
            <span className="details-skeleton-title skeleton-shimmer" />
            <span className="details-skeleton-title short skeleton-shimmer" />

            <div className="details-facts">
              <span className="details-skeleton-pill skeleton-shimmer" />
              <span className="details-skeleton-pill skeleton-shimmer" />
              <span className="details-skeleton-pill skeleton-shimmer" />
            </div>

            <div className="genre-list">
              <span className="details-skeleton-chip skeleton-shimmer" />
              <span className="details-skeleton-chip skeleton-shimmer" />
              <span className="details-skeleton-chip skeleton-shimmer" />
            </div>

            <span className="details-skeleton-copy-line skeleton-shimmer" />
            <span className="details-skeleton-copy-line skeleton-shimmer" />
            <span className="details-skeleton-copy-line short skeleton-shimmer" />
          </div>
        </div>
      </section>
    </main>
  );
}

export default function TVDetails({ collections, onSeriesViewed }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const hasValidId = /^\d+$/.test(id || "");

  const [seriesState, setSeriesState] = useState({
    id: null,
    series: null,
    error: "",
  });

  const isLoading = hasValidId && seriesState.id !== id;
  const series = seriesState.id === id ? seriesState.series : null;
  const error = seriesState.id === id ? seriesState.error : "";

  // Fetch Series Details
  useEffect(() => {
    const controller = new AbortController();

    if (!hasValidId) {
      return () => controller.abort();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });

    getTVDetails(id, { signal: controller.signal })
      .then((data) => {
        setSeriesState({ id, series: data, error: "" });
        if (onSeriesViewed) {
          onSeriesViewed({ ...data, media_type: "tv" });
        }
      })
      .catch((err) => {
        if (err.name !== "CanceledError" && err.code !== "ERR_CANCELED") {
          const detail = err.response?.data?.detail;
          setSeriesState({
            id,
            series: null,
            error:
              typeof detail === "string"
                ? detail
                : "Unable to load series details.",
          });
        }
      });

    return () => controller.abort();
  }, [hasValidId, id, onSeriesViewed]);



  // Update page title
  useEffect(() => {
    if (!series?.name) return undefined;
    const prevTitle = document.title;
    document.title = `${series.name} — CineMatch TV`;
    return () => {
      document.title = prevTitle;
    };
  }, [series]);

  if (!hasValidId || (!isLoading && (error || !series))) {
    return (
      <main className="details-state-page">
        <div className="details-error" role="alert">
          <div className="details-error-icon">
            <TvIcon />
          </div>
          <p className="details-kicker">Something went off script</p>
          <h1>TV series details unavailable</h1>
          <p>{error || "We couldn't find that TV series."}</p>
          <div className="details-actions">
            <button
              type="button"
              className="details-button details-button-primary"
              onClick={() => navigate("/tv")}
            >
              <ArrowLeftIcon /> Back to TV Series
            </button>
            <Link className="details-button details-button-secondary" to="/">
              Go to Home
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (isLoading) {
    return <TVDetailsSkeleton />;
  }

  const rating =
    typeof series.vote_average === "number" && series.vote_average > 0
      ? series.vote_average.toFixed(1)
      : "NR";

  const firstAirYear = series.first_air_date
    ? series.first_air_date.slice(0, 4)
    : "Year unavailable";
  const lastAirYear = series.last_air_date
    ? series.last_air_date.slice(0, 4)
    : "";
  const yearsDisplay =
    lastAirYear && lastAirYear !== firstAirYear
      ? `${firstAirYear} – ${lastAirYear}`
      : firstAirYear;

  const tvItem = { ...series, media_type: "tv", name: series.name };
  const isFavorite = collections?.isFavorite ? collections.isFavorite(tvItem) : false;
  const isWatchlisted = collections?.isWatchlisted ? collections.isWatchlisted(tvItem) : false;

  return (
    <main className="details-page tv-details-page">
      <section className="details-hero">
        {series.backdrop_url && (
          <img
            className="details-backdrop"
            src={series.backdrop_url}
            alt=""
            aria-hidden="true"
          />
        )}
        <div className="details-backdrop-shade" />

        <nav className="details-nav details-container" aria-label="TV navigation">
          <Link className="back-link" to="/tv">
            <ArrowLeftIcon /> Back to TV Series
          </Link>
          <div className="details-nav-right">
            <Link className="details-nav-link" to="/">
              Movies
            </Link>
            <Link className="details-nav-link is-current" to="/tv">
              TV Series
            </Link>
            <Link className="details-nav-link" to="/favorites">
              Favorites
            </Link>
            <Link className="details-nav-link" to="/watchlist">
              Watchlist
            </Link>
            <Link className="details-brand" to="/">
              <FilmIcon /> CineMatch
            </Link>
          </div>
        </nav>

        <div className="details-layout details-container">
          <div className="details-poster">
            {series.poster_url ? (
              <img src={series.poster_url} alt={`${series.name} poster`} />
            ) : (
              <div className="details-poster-placeholder">
                <TvIcon />
                <span>No Poster</span>
              </div>
            )}
          </div>

          <div className="details-copy">
            <p className="details-kicker">
              {series.status || "TV Series"}
            </p>
            <h1>{series.name}</h1>

            <div className="details-facts" aria-label="Series facts">
              <span>{yearsDisplay}</span>
              {series.number_of_seasons != null && (
                <span>
                  {series.number_of_seasons}{" "}
                  {series.number_of_seasons === 1 ? "Season" : "Seasons"}
                </span>
              )}
              {series.number_of_episodes != null && (
                <span>{series.number_of_episodes} Episodes</span>
              )}
              <span className="details-rating">
                <b aria-hidden="true">★</b> {rating} <small>/ 10</small>
              </span>
            </div>

            {Array.isArray(series.genres) && series.genres.length > 0 && (
              <div className="genre-list" aria-label="Genres">
                {series.genres.map((genre) => (
                  <span key={genre}>{genre}</span>
                ))}
              </div>
            )}

            <p className="details-overview">
              {series.overview || "No overview is available for this TV series."}
            </p>

            {/* Creators & Networks */}
            <div className="tv-meta-lines">
              {Array.isArray(series.created_by) && series.created_by.length > 0 && (
                <div className="director-line">
                  <span>Created by</span>
                  <strong>{series.created_by.join(", ")}</strong>
                </div>
              )}

              {Array.isArray(series.networks) && series.networks.length > 0 && (
                <div className="networks-line">
                  <span>Network</span>
                  <div className="network-badges">
                    {series.networks.map((net, idx) => (
                      <span className="network-badge" key={net.name || idx}>
                        {net.logo_url ? (
                          <img
                            src={net.logo_url}
                            alt={net.name}
                            className="network-logo"
                          />
                        ) : (
                          net.name
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Actions: Save buttons & Trailer */}
            <div className="details-actions">
              {series.trailer_url && (
                <a
                  className="details-button details-button-primary"
                  href={series.trailer_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <PlayIcon /> Watch Trailer
                </a>
              )}

              {collections && (
                <>
                  <button
                    type="button"
                    className={`details-button details-button-secondary ${
                      isFavorite ? "is-active-btn" : ""
                    }`}
                    onClick={() => collections.toggleFavorite(tvItem)}
                  >
                    <HeartIcon />{" "}
                    {isFavorite ? "In Favorites" : "Add to Favorites"}
                  </button>

                  <button
                    type="button"
                    className={`details-button details-button-secondary ${
                      isWatchlisted ? "is-active-btn" : ""
                    }`}
                    onClick={() => collections.toggleWatchlist(tvItem)}
                  >
                    <BookmarkIcon />{" "}
                    {isWatchlisted ? "In Watchlist" : "Add to Watchlist"}
                  </button>
                </>
              )}

              <Link className="details-button details-button-secondary" to="/tv">
                <ArrowLeftIcon /> Back to TV Series
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Cast Section */}
      <section className="cast-section details-container">
        <div className="cast-heading">
          <div>
            <p className="details-kicker">Series Ensemble</p>
            <h2>Top Cast</h2>
          </div>
          {Array.isArray(series.cast) && (
            <span>{series.cast.length} cast members</span>
          )}
        </div>

        {Array.isArray(series.cast) && series.cast.length > 0 ? (
          <div className="cast-grid">
            {series.cast.map((member, index) => (
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
