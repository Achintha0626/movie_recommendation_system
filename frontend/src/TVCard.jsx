import { Link } from "react-router-dom";

function TvIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
      <polyline points="17 2 12 7 7 2" />
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

export default function TVCard({
  series,
  collections,
  onRemove,
  removeLabel = "Remove",
  showRecommendationInfo = false,
}) {
  const seriesName = series.name || series.title || "Untitled Series";
  const firstAirYear = series.first_air_date
    ? series.first_air_date.slice(0, 4)
    : series.release_date
    ? series.release_date.slice(0, 4)
    : "Year unavailable";
  const rating =
    typeof series.vote_average === "number" && series.vote_average > 0
      ? series.vote_average.toFixed(1)
      : "NR";

  const matchScore =
    typeof series.match_score === "number" && series.match_score > 0
      ? Math.max(0, Math.min(100, Math.round(series.match_score)))
      : typeof series.similarity_score === "number" && series.similarity_score > 0
      ? Math.max(0, Math.min(100, Math.round(series.similarity_score * 100)))
      : null;

  const canSave = series.id != null;
  const tvItem = { ...series, media_type: "tv", name: seriesName };
  const favoriteIsActive =
    canSave && collections?.isFavorite ? collections.isFavorite(tvItem) : false;
  const watchlistIsActive =
    canSave && collections?.isWatchlisted ? collections.isWatchlisted(tvItem) : false;

  const genreDisplay = Array.isArray(series.genres)
    ? series.genres.join(", ")
    : typeof series.genres === "string"
    ? series.genres
    : "";

  const content = (
    <>
      <div className="poster-art">
        {series.poster_url ? (
          <img
            src={series.poster_url}
            alt={`${seriesName} poster`}
            loading="lazy"
          />
        ) : (
          <div
            className="no-poster"
            role="img"
            aria-label="No poster available"
          >
            <TvIcon />
            <span>No Poster</span>
          </div>
        )}
        <span className="media-type-badge tv-badge">TV Series</span>
      </div>

      <div className="movie-details">
        <h3 title={seriesName}>{seriesName}</h3>
        <div className="movie-meta">
          <span>{firstAirYear}</span>
          <span aria-label={`TMDB rating ${rating} out of 10`}>
            <b aria-hidden="true">★</b> {rating}
          </span>
          {series.number_of_seasons != null && series.number_of_seasons > 0 && (
            <span className="season-pill">
              {series.number_of_seasons} {series.number_of_seasons === 1 ? "Season" : "Seasons"}
            </span>
          )}
        </div>

        {genreDisplay && (
          <p className="tv-card-genres" title={genreDisplay}>
            {genreDisplay}
          </p>
        )}

        {series.overview && <p className="movie-overview">{series.overview}</p>}

        {showRecommendationInfo && matchScore !== null && matchScore > 0 && (
          <div className="recommendation-explanation">
            <div className="match-heading">
              <span className="match-score-badge">{matchScore}% Match</span>
              <span>Semantic Similarity</span>
            </div>
          </div>
        )}

        <span className="card-action">
          {series.id ? "View series details →" : "Details unavailable"}
        </span>
      </div>
    </>
  );

  return (
    <article className="movie-card tv-card">
      {collections && (
        <div className="card-save-actions" aria-label="Save TV series">
          <button
            className={`card-save-button favorite-button ${
              favoriteIsActive ? "is-active" : ""
            }`}
            type="button"
            aria-label={
              favoriteIsActive
                ? "Remove from favorites"
                : "Add to favorites"
            }
            aria-pressed={favoriteIsActive}
            title={
              canSave
                ? favoriteIsActive
                  ? "Remove from favorites"
                  : "Add to favorites"
                : "Series ID unavailable"
            }
            disabled={!canSave}
            onClick={() => collections.toggleFavorite(tvItem)}
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
                : "Series ID unavailable"
            }
            disabled={!canSave}
            onClick={() => collections.toggleWatchlist(tvItem)}
          >
            <BookmarkIcon />
          </button>
        </div>
      )}

      {series.id ? (
        <Link
          className="movie-card-main movie-card-link"
          to={`/tv/${series.id}`}
          aria-label={`View details for ${seriesName}`}
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
          onClick={() => onRemove(tvItem)}
        >
          <TrashIcon /> {removeLabel}
        </button>
      )}
    </article>
  );
}
