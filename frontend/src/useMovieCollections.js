import { useCallback, useEffect, useState } from "react";

const FAVORITES_KEY = "favorites";
const WATCHLIST_KEY = "watchlist";

/**
 * Returns a unique compound key for a media item (movie or tv series)
 * to prevent ID collisions when both media types share the same numeric ID.
 */
export function getMediaKey(itemOrId, defaultType = "movie") {
  if (itemOrId == null) return null;
  if (typeof itemOrId === "object") {
    if (itemOrId.id == null) return null;
    const type =
      itemOrId.media_type || (itemOrId.name && !itemOrId.title ? "tv" : "movie");
    return `${type}:${itemOrId.id}`;
  }

  const str = String(itemOrId);
  if (str.startsWith("movie:") || str.startsWith("tv:")) {
    return str;
  }
  return `${defaultType}:${str}`;
}

/**
 * Normalizes both movie and tv objects into a consistent shape that satisfies
 * existing movie components (expecting title/release_date) and new TV components
 * (expecting name/first_air_date).
 */
export function prepareMediaItem(item) {
  if (!item || item.id == null) return null;

  const id = typeof item.id === "number" ? item.id : Number(item.id) || item.id;
  const isTV =
    item.media_type === "tv" || (!item.title && Boolean(item.name));
  const media_type = isTV ? "tv" : "movie";
  const title = item.title || item.name || "Untitled";
  const name = item.name || item.title || "Untitled";
  const release_date = item.release_date || item.first_air_date || "";
  const first_air_date = item.first_air_date || item.release_date || "";

  return {
    id,
    media_type,
    title,
    name,
    poster_url: item.poster_url || null,
    backdrop_url: item.backdrop_url || null,
    release_date,
    first_air_date,
    vote_average:
      typeof item.vote_average === "number" ? item.vote_average : null,
    overview: item.overview || "",
    genres: item.genres || "",
  };
}

function parseCollection(value) {
  try {
    const rawItems = JSON.parse(value || "[]");
    if (!Array.isArray(rawItems)) return [];

    const seenKeys = new Set();
    return rawItems.reduce((collection, rawItem) => {
      const prepared = prepareMediaItem(rawItem);
      const key = getMediaKey(prepared);

      if (!prepared || !key || seenKeys.has(key)) return collection;

      seenKeys.add(key);
      collection.push(prepared);
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

function persistCollection(key, items) {
  try {
    window.localStorage.setItem(key, JSON.stringify(items));
  } catch {
    // The UI remains usable if storage is unavailable or full.
  }
}

function toggleItem(setCollection, item) {
  const prepared = prepareMediaItem(item);
  const key = getMediaKey(prepared);
  if (!prepared || !key) return;

  setCollection((currentItems) => {
    const alreadySaved = currentItems.some(
      (savedItem) => getMediaKey(savedItem) === key,
    );

    return alreadySaved
      ? currentItems.filter((savedItem) => getMediaKey(savedItem) !== key)
      : [...currentItems, prepared];
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

  const toggleFavorite = useCallback((item) => {
    toggleItem(setFavorites, item);
  }, []);

  const toggleWatchlist = useCallback((item) => {
    toggleItem(setWatchlist, item);
  }, []);

  const removeFavorite = useCallback((itemOrId, maybeMediaType) => {
    const key = getMediaKey(itemOrId, maybeMediaType || "movie");
    setFavorites((items) =>
      items.filter((item) => getMediaKey(item) !== key),
    );
  }, []);

  const removeFromWatchlist = useCallback((itemOrId, maybeMediaType) => {
    const key = getMediaKey(itemOrId, maybeMediaType || "movie");
    setWatchlist((items) =>
      items.filter((item) => getMediaKey(item) !== key),
    );
  }, []);

  const isFavorite = useCallback(
    (itemOrId, maybeMediaType) => {
      const key = getMediaKey(itemOrId, maybeMediaType || "movie");
      return favorites.some((item) => getMediaKey(item) === key);
    },
    [favorites],
  );

  const isWatchlisted = useCallback(
    (itemOrId, maybeMediaType) => {
      const key = getMediaKey(itemOrId, maybeMediaType || "movie");
      return watchlist.some((item) => getMediaKey(item) === key);
    },
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
