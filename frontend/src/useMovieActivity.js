import { useCallback, useEffect, useState } from "react";

const RECENTLY_VIEWED_KEY = "recentlyViewed";
const RECOMMENDATION_HISTORY_KEY = "recommendationHistory";
const MAX_ITEMS = 10;

function movieId(movie) {
  return movie?.id == null ? null : String(movie.id);
}

function prepareMovie(movie, includeRecommendationData = false) {
  if (!movie || !movie.title) return null;

  const prepared = {
    id: movie.id ?? null,
    title: movie.title,
    poster_url: movie.poster_url || null,
    release_date: movie.release_date || "",
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
  const seenIds = new Set();

  return parseJson(value)
    .reduce((movies, movie) => {
      const prepared = prepareMovie(movie);
      const id = movieId(prepared);

      if (!prepared || !id || seenIds.has(id)) return movies;

      seenIds.add(id);
      movies.push(prepared);
      return movies;
    }, [])
    .slice(0, MAX_ITEMS);
}

function historyKey(item) {
  const movie = item.searchedMovie.trim().toLocaleLowerCase();
  const genre = item.selectedGenre.trim().toLocaleLowerCase();
  return `${movie}::${genre}`;
}

function prepareHistoryItem(item) {
  if (
    !item ||
    typeof item.searchedMovie !== "string" ||
    !item.searchedMovie.trim() ||
    !Array.isArray(item.recommendations)
  ) {
    return null;
  }

  const recommendations = item.recommendations
    .map((movie) => prepareMovie(movie, true))
    .filter(Boolean);

  return {
    searchedMovie: item.searchedMovie.trim(),
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

  const addRecentlyViewed = useCallback((movie) => {
    const prepared = prepareMovie(movie);
    const id = movieId(prepared);
    if (!prepared || !id) return;

    setRecentlyViewed((movies) => [
      prepared,
      ...movies.filter((savedMovie) => movieId(savedMovie) !== id),
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

  const removeHistoryItem = useCallback((searchedMovie, selectedGenre) => {
    const key = historyKey({ searchedMovie, selectedGenre });
    setRecommendationHistory((history) =>
      history.filter((item) => historyKey(item) !== key),
    );
  }, []);

  const clearRecommendationHistory = useCallback(() => {
    setRecommendationHistory([]);
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
