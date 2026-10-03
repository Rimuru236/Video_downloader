// src/services/api.js — centralized API client

// Default to a same-origin relative path, not a hardcoded "localhost:8000".
// Both vite.config.mjs (dev server) and nginx.conf (Docker/production) already
// proxy "/api" to the backend, and modern browsers resolve relative URLs
// (including WebSocket ones — see connectProgressWS below) against the
// current page origin automatically. A hardcoded absolute localhost URL
// bypasses both proxies and only ever worked when the frontend happened to be
// opened on the exact same machine the backend is listening on — it silently
// breaks the moment the app is accessed from any other host (e.g. a second
// machine on the LAN, or a real domain in a docker-compose deployment).
// Set VITE_API_URL explicitly only if the backend is served from a different
// origin than the frontend.
const BASE = import.meta.env.VITE_API_URL || "/api/v1";

// The backend's api_key setting (see backend/utils/auth.py) is a shared
// secret the *client* must present, not something the server hands out —
// there's no login flow, so it's entered once in Settings and kept in
// localStorage. When the backend has no api_key configured (the default),
// it ignores this header entirely, so an empty key here is harmless.
const API_KEY_STORAGE_KEY = "sv_api_key";

export function getApiKey() {
  try {
    return localStorage.getItem(API_KEY_STORAGE_KEY) || "";
  } catch {
    return ""; // localStorage unavailable (e.g. privacy mode) — fall back to unauthenticated
  }
}

export function setApiKey(key) {
  try {
    if (key) localStorage.setItem(API_KEY_STORAGE_KEY, key);
    else localStorage.removeItem(API_KEY_STORAGE_KEY);
  } catch {
    // ignore — nothing sensible to do if storage is unavailable
  }
}

async function req(method, path, body) {
  try {
    const apiKey = getApiKey();
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      if (res.status === 401) {
        throw new Error("Invalid or missing API key — set it under Settings → Security");
      }
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  } catch (e) {
    // Network errors (backend not running etc.) — rethrow cleanly
    throw new Error(e.message || "Network error");
  }
}

export const api = {
  // Downloads
  createDownload:  (body)        => req("POST",   "/download",        body),
  batchDownload:   (body)        => req("POST",   "/download/batch",  body),
  batchSubtitleDownload: (body)  => req("POST",   "/download/subtitles/batch", body),
  listDownloads:   (params = "") => req("GET",    `/downloads${params ? "?" + params : ""}`),
  getDownload:     (id)          => req("GET",    `/download/${id}`),
  pauseDownload:   (id)          => req("POST",   `/download/${id}/pause`),
  resumeDownload:  (id)          => req("POST",   `/download/${id}/resume`),
  cancelDownload:  (id)          => req("POST",   `/download/${id}/cancel`),
  retryDownload:   (id)          => req("POST",   `/download/${id}/retry`),
  deleteDownload:  (id, opts = {}) => req("DELETE", `/download/${id}${opts.deleteFiles ? "?delete_files=true" : ""}`),

  // Queue
  listQueue:       ()            => req("GET",    "/queue"),
  addToQueue:      (body)        => req("POST",   "/queue/add",       body),
  startQueue:      ()            => req("POST",   "/queue/start"),
  pauseQueue:      ()            => req("POST",   "/queue/pause"),
  clearQueue:      ()            => req("POST",   "/queue/clear"),
  reorderQueue:    (body)        => req("POST",   "/queue/reorder",   body),
  removeFromQueue: (id)          => req("DELETE", `/queue/${id}`),

  // Metadata
  fetchMetadata:   (url)         => req("POST",   "/metadata",        { url }),
  fetchFormats:    (url)         => req("GET",    `/metadata/formats?url=${encodeURIComponent(url)}`),

  // Settings
  getSettings:     ()            => req("GET",    "/settings"),
  updateSetting:   (key, value)  => req("POST",   "/settings/update", { key, value }),
  bulkSettings:    (updates)     => req("POST",   "/settings/bulk",   updates),

  // Logs & Analytics
  getLogs:         (params = "") => req("GET",    `/logs${params ? "?" + params : ""}`),
  getLogFile:      ()            => fetch(`${BASE}/logs/file`, { headers: _authHeader() }).then(r => r.text()),
  exportLogs:      ()            => fetch(`${BASE}/logs/export`, { headers: _authHeader() }).then(r => r.text()),
  getAnalytics:    ()            => req("GET",    "/analytics/summary"),
  getAnalyticsDetailed: ()       => req("GET",    "/analytics/detailed"),
};

function _authHeader() {
  const apiKey = getApiKey();
  return apiKey ? { "X-API-Key": apiKey } : {};
}

// FE-2: "Open file" needs the X-API-Key header when auth is enabled, and a
// plain <a href> or window.open(url) navigation can't attach custom headers
// (same browser limitation as the WebSocket handshake) — so this fetches
// the file as a blob with the header attached, then opens an object URL
// instead of the real endpoint URL. Trade-off: the whole file is pulled
// into browser memory before it opens, which is fine for the "quickly play
// or grab a completed download" use case this button is for, not ideal for
// very large files — a signed short-lived download link would avoid that,
// but is more than this needs today.
export async function openDownloadedFile(id) {
  const res = await fetch(`${BASE}/download/${id}/file`, { headers: _authHeader() });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "File not found on disk" : `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

// WebSocket helper
export function connectProgressWS(downloadId, onMessage) {
  const wsBase = BASE.replace("http", "ws");
  const apiKey = getApiKey();
  // Browsers can't attach custom headers to a WebSocket handshake, so the
  // key travels as a query param instead — see ws_api_key_ok() on the backend.
  const keyParam = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
  const ws = new WebSocket(`${wsBase}/ws/download/${downloadId}${keyParam}`);
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    // Handle ping/pong keep-alive messages
    if (data.type === "ping") {
      // Automatically respond to keep connection alive
      ws.send(JSON.stringify({ type: "pong" }));
      return;
    }
    onMessage(data);
  };
  return ws;
}
