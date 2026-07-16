import axios from "axios";

const DEFAULT_API_BASE_URL = import.meta.env.DEV
  ? "http://127.0.0.1:8000"
  : "https://movie-recommendation-system-do3f.onrender.com";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

function isRecommendationRequest(config) {
  return String(config.url || "").startsWith("/recommend/");
}

function resolvedRequestUrl(config) {
  const url = new URL(config.url || "", config.baseURL || API_BASE_URL);
  const params = new URLSearchParams();

  Object.entries(config.params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.append(key, value);
    }
  });

  if ([...params].length > 0) {
    url.search = params.toString();
  }

  return url.toString();
}

if (import.meta.env.DEV) {
  console.info(`[CineMatch API] Base URL: ${API_BASE_URL}`);

  apiClient.interceptors.request.use((config) => {
    if (isRecommendationRequest(config)) {
      config.cineMatchTiming = {
        startedAt: performance.now(),
        url: resolvedRequestUrl(config),
      };

      console.debug(
        "[CineMatch API] Recommendation request started",
        {
          url: config.cineMatchTiming.url,
          startTime: `${config.cineMatchTiming.startedAt.toFixed(2)} ms`,
        },
      );
    }

    return config;
  });

  apiClient.interceptors.response.use(
    (response) => {
      const timing = response.config.cineMatchTiming;

      if (timing) {
        console.debug(
          "[CineMatch API] Recommendation response received",
          {
            url: timing.url,
            responseTime: `${(performance.now() - timing.startedAt).toFixed(2)} ms`,
            status: response.status,
          },
        );
      }

      return response;
    },
    (error) => {
      const timing = error.config?.cineMatchTiming;

      if (timing) {
        console.debug(
          "[CineMatch API] Recommendation response failed",
          {
            url: timing.url,
            responseTime: `${(performance.now() - timing.startedAt).toFixed(2)} ms`,
            status: error.response?.status ?? "network/canceled",
          },
        );
      }

      return Promise.reject(error);
    },
  );
}
