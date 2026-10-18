import { apiClient } from "./config";

/**
 * Dedicated TV API service module.
 * Reuses the existing apiClient instance and base URL configuration.
 */

/**
 * Fetch a paginated list of TV series from the backend catalogue.
 * @param {Object} options
 * @param {number} [options.page=1]
 * @param {number} [options.pageSize=20]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<{results: Array, page: number, page_size: number, total: number, total_pages: number}>}
 */
export async function listTVSeries({ page = 1, pageSize = 20, signal } = {}) {
  const response = await apiClient.get("/tv", {
    params: { page, page_size: pageSize },
    signal,
  });
  return response.data;
}

/**
 * Search the TV catalogue by series name.
 * @param {string} query
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<{results: Array}>}
 */
export async function searchTVSeries(query, { signal } = {}) {
  const trimmed = (query || "").trim();
  if (!trimmed) {
    return { results: [] };
  }
  const response = await apiClient.get("/tv/search", {
    params: { query: trimmed },
    signal,
  });
  return response.data;
}

/**
 * Fetch trending TV series from TMDB via the backend proxy.
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<{results: Array}>}
 */
export async function getTrendingTVSeries({ signal } = {}) {
  const response = await apiClient.get("/tv/trending", {
    signal,
  });
  return response.data;
}

/**
 * Fetch full TV series details from TMDB via the backend.
 * @param {number|string} seriesId
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<Object>}
 */
export async function getTVDetails(seriesId, { signal } = {}) {
  const response = await apiClient.get(`/tv/${seriesId}`, {
    signal,
  });
  return response.data;
}

/**
 * Fetch semantic TV series recommendations based on embeddings.
 * @param {number|string} seriesId
 * @param {Object} [options]
 * @param {number} [options.limit=10]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<{series_id: number, series_name: string|null, recommendations: Array}>}
 */
export async function getTVRecommendations(seriesId, { limit = 10, signal } = {}) {
  const response = await apiClient.get(`/tv/recommend/${seriesId}`, {
    params: { limit },
    signal,
  });
  return response.data;
}
