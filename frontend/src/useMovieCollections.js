import { useCallback, useEffect, useState } from "react";

const FAVORITES_KEY = "favorites";
const WATCHLIST_KEY = "watchlist";

function movieId(movie) {
  return movie?.id == null ? null : String(movie.id);
}

function prepareMovie(movie) {
  if (!movieId(movie)) return null;

  return {
    id: movie.id,
    title: movie.title || "Untitled",
    poster_url: movie.poster_url || null,
    backdrop_url: movie.backdrop_url || null,
    release_date: movie.release_date || "",
    vote_average:
      typeof movie.vote_average === "number" ? movie.vote_average : null,
    overview: movie.overview || "",
  };
}

function parseCollection(value) {
  try {
    const movies = JSON.parse(value || "[]");
    if (!Array.isArray(movies)) return [];

    const seenIds = new Set();
    return movies.reduce((collection, movie) => {
      const preparedMovie = prepareMovie(movie);
      const id = movieId(preparedMovie);

      if (!preparedMovie || seenIds.has(id)) return collection;

      seenIds.add(id);
      collection.push(preparedMovie);
      return collection;
    }, []);
  } catch {
    return [];
  }
}

function readCollection(key) {
  try {
    return parseCollection(window.localStorage.getItem(key));
  } catch {
    return [];
  }
}

function persistCollection(key, movies) {
  try {
    window.localStorage.setItem(key, JSON.stringify(movies));
  } catch {
    // The UI remains usable if storage is unavailable or full.
  }
}

function toggleMovie(setCollection, movie) {
  const preparedMovie = prepareMovie(movie);
  const id = movieId(preparedMovie);
  if (!preparedMovie || !id) return;

  setCollection((currentMovies) => {
    const alreadySaved = currentMovies.some(
      (savedMovie) => movieId(savedMovie) === id,
    );

    return alreadySaved
      ? currentMovies.filter((savedMovie) => movieId(savedMovie) !== id)
      : [...currentMovies, preparedMovie];
  });
}

export default function useMovieCollections() {
  const [favorites, setFavorites] = useState(() =>
    readCollection(FAVORITES_KEY),
  );
  const [watchlist, setWatchlist] = useState(() =>
    readCollection(WATCHLIST_KEY),
  );

  useEffect(() => {
    persistCollection(FAVORITES_KEY, favorites);
  }, [favorites]);

  useEffect(() => {
    persistCollection(WATCHLIST_KEY, watchlist);
  }, [watchlist]);

  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key === FAVORITES_KEY) {
        setFavorites(parseCollection(event.newValue));
      } else if (event.key === WATCHLIST_KEY) {
        setWatchlist(parseCollection(event.newValue));
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const toggleFavorite = useCallback((movie) => {
    toggleMovie(setFavorites, movie);
  }, []);

  const toggleWatchlist = useCallback((movie) => {
    toggleMovie(setWatchlist, movie);
  }, []);

  const removeFavorite = useCallback((id) => {
    setFavorites((movies) =>
      movies.filter((movie) => movieId(movie) !== String(id)),
    );
  }, []);

  const removeFromWatchlist = useCallback((id) => {
    setWatchlist((movies) =>
      movies.filter((movie) => movieId(movie) !== String(id)),
    );
  }, []);

  const isFavorite = useCallback(
    (id) => favorites.some((movie) => movieId(movie) === String(id)),
    [favorites],
  );

  const isWatchlisted = useCallback(
    (id) => watchlist.some((movie) => movieId(movie) === String(id)),
    [watchlist],
  );

  return {
    favorites,
    watchlist,
    toggleFavorite,
    toggleWatchlist,
    removeFavorite,
    removeFromWatchlist,
    isFavorite,
    isWatchlisted,
  };
}
