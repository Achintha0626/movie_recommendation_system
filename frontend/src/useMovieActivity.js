import { useCallback, useEffect, useState } from "react";

const RECENTLY_VIEWED_KEY = "recentlyViewed";
const RECOMMENDATION_HISTORY_KEY = "recommendationHistory";
const MAX_ITEMS = 10;

function activityItemKey(item) {
  if (!item || item.id == null) return null;
  const type =
    item.media_type || (item.name && !item.title ? "tv" : "movie");
  return `${type}:${item.id}`;
}

function prepareMovie(movie, includeRecommendationData = false) {
  if (!movie || (!movie.title && !movie.name)) return null;

  const isTV =
    movie.media_type === "tv" || (!movie.title && Boolean(movie.name));
  const media_type = isTV ? "tv" : "movie";
  const title = movie.title || movie.name || "Untitled";
  const name = movie.name || movie.title || "Untitled";
  const release_date = movie.release_date || movie.first_air_date || "";
  const first_air_date = movie.first_air_date || movie.release_date || "";

  const prepared = {
    id: movie.id ?? null,
    media_type,
    title,
    name,
    poster_url: movie.poster_url || null,
    release_date,
    first_air_date,
    vote_average:
      typeof movie.vote_average === "number" ? movie.vote_average : null,
    overview: movie.overview || "",
  };

  if (includeRecommendationData) {
    prepared.match_score =
      typeof movie.match_score === "number" ? movie.match_score : 0;
    prepared.reasons = Array.isArray(movie.reasons)
      ? movie.reasons.filter((reason) => typeof reason === "string" && reason)
      : ["Similar story overview"];
    prepared.explanation =
      typeof movie.explanation === "string" ? movie.explanation.trim() : "";
  }

  return prepared;
}

function parseJson(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normalizeRecentlyViewed(value) {
  const seenKeys = new Set();

  return parseJson(value)
    .reduce((items, item) => {
      const prepared = prepareMovie(item);
      const key = activityItemKey(prepared);

      if (!prepared || !key || seenKeys.has(key)) return items;

      seenKeys.add(key);
      items.push(prepared);
      return items;
    }, [])
    .slice(0, MAX_ITEMS);
}

function historyKey(item) {
  if (!item) return "";
  const type =
    item.media_type || (item.name && !item.title ? "tv" : "movie");
  const movie = (
    item.searchedMovie ||
    item.searchedTitle ||
    item.name ||
    item.title ||
    ""
  )
    .trim()
    .toLocaleLowerCase();
  const genre = (item.selectedGenre || "All").trim().toLocaleLowerCase();
  return `${type}::${movie}::${genre}`;
}

function prepareHistoryItem(item) {
  const searchedTitle =
    typeof item?.searchedMovie === "string" && item.searchedMovie.trim()
      ? item.searchedMovie.trim()
      : typeof item?.searchedTitle === "string" && item.searchedTitle.trim()
      ? item.searchedTitle.trim()
      : typeof item?.name === "string" && item.name.trim()
      ? item.name.trim()
      : typeof item?.title === "string" && item.title.trim()
      ? item.title.trim()
      : "";

  if (!searchedTitle || !Array.isArray(item?.recommendations)) {
    return null;
  }

  const recommendations = item.recommendations
    .map((movie) => prepareMovie(movie, true))
    .filter(Boolean);

  const media_type =
    item.media_type === "tv" ||
    (recommendations.length > 0 &&
      recommendations.some((rec) => rec.media_type === "tv"))
      ? "tv"
      : "movie";

  return {
    media_type,
    searchedMovie: searchedTitle,
    selectedGenre:
      typeof item.selectedGenre === "string" && item.selectedGenre.trim()
        ? item.selectedGenre.trim()
        : "All",
    recommendations,
    createdAt: Number.isFinite(Number(item.createdAt))
      ? Number(item.createdAt)
      : Date.now(),
  };
}

function normalizeHistory(value) {
  const seenSearches = new Set();

  return parseJson(value)
    .reduce((history, item) => {
      const prepared = prepareHistoryItem(item);
      if (!prepared) return history;

      const key = historyKey(prepared);
      if (seenSearches.has(key)) return history;

      seenSearches.add(key);
      history.push(prepared);
      return history;
    }, [])
    .slice(0, MAX_ITEMS);
}

function readStorage(key, normalizer) {
  try {
    return normalizer(window.localStorage.getItem(key));
  } catch {
    return [];
  }
}

function persistStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Browsing remains functional when storage is unavailable or full.
  }
}

export default function useMovieActivity() {
  const [recentlyViewed, setRecentlyViewed] = useState(() =>
    readStorage(RECENTLY_VIEWED_KEY, normalizeRecentlyViewed),
  );
  const [recommendationHistory, setRecommendationHistory] = useState(() =>
    readStorage(RECOMMENDATION_HISTORY_KEY, normalizeHistory),
  );

  useEffect(() => {
    persistStorage(RECENTLY_VIEWED_KEY, recentlyViewed);
  }, [recentlyViewed]);

  useEffect(() => {
    persistStorage(RECOMMENDATION_HISTORY_KEY, recommendationHistory);
  }, [recommendationHistory]);

  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key === RECENTLY_VIEWED_KEY) {
        setRecentlyViewed(normalizeRecentlyViewed(event.newValue));
      } else if (event.key === RECOMMENDATION_HISTORY_KEY) {
        setRecommendationHistory(normalizeHistory(event.newValue));
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const addRecentlyViewed = useCallback((item) => {
    const prepared = prepareMovie(item);
    const key = activityItemKey(prepared);
    if (!prepared || !key) return;

    setRecentlyViewed((items) => [
      prepared,
      ...items.filter((savedItem) => activityItemKey(savedItem) !== key),
    ].slice(0, MAX_ITEMS));
  }, []);

  const addRecommendationHistory = useCallback((item) => {
    const prepared = prepareHistoryItem({ ...item, createdAt: Date.now() });
    if (!prepared || prepared.recommendations.length === 0) return;

    const key = historyKey(prepared);
    setRecommendationHistory((history) => [
      prepared,
      ...history.filter((entry) => historyKey(entry) !== key),
    ].slice(0, MAX_ITEMS));
  }, []);

  const removeHistoryItem = useCallback(
    (searchedMovie, selectedGenre, mediaType = "movie") => {
      let target;
      if (typeof searchedMovie === "object" && searchedMovie !== null) {
        target = searchedMovie;
      } else {
        target = {
          searchedMovie,
          selectedGenre,
          media_type: mediaType,
        };
      }
      const key = historyKey(target);
      setRecommendationHistory((history) =>
        history.filter((item) => historyKey(item) !== key),
      );
    },
    [],
  );

  const clearRecommendationHistory = useCallback((mediaType) => {
    if (
      typeof mediaType === "string" &&
      (mediaType === "tv" || mediaType === "movie")
    ) {
      setRecommendationHistory((history) =>
        history.filter((item) => (item.media_type || "movie") !== mediaType),
      );
    } else {
      setRecommendationHistory([]);
    }
  }, []);

  return {
    recentlyViewed,
    recommendationHistory,
    addRecentlyViewed,
    addRecommendationHistory,
    removeHistoryItem,
    clearRecommendationHistory,
  };
}
