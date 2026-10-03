// src/store/useStore.js — Zustand global state
import { create } from "zustand";
import { api } from "../services/api";

export const useStore = create((set, get) => ({
  // Downloads
  downloads: [],
  loadingDl: false,
  // `opts` is a plain options bag — { userInitiated, query } — NOT a query
  // string. `query`, if given, is the literal query string forwarded to the
  // API (e.g. "status=failed"); `userInitiated` only controls whether a
  // failed fetch surfaces a toast. Previously the whole `opts` object was
  // passed straight through to api.listDownloads(), which string-concatenated
  // it into "?[object Object]" whenever callers passed { userInitiated: true }.
  fetchDownloads: async (opts) => {
    set({ loadingDl: true });
    try {
      const data = await api.listDownloads(opts?.query);
      set({ downloads: data });
    } catch (error) {
      console.error('Failed to fetch downloads:', error.message);
      // Only show toast for user-initiated refreshes, not periodic polling
      if (opts && opts.userInitiated) {
        get().toast(`Failed to load downloads: ${error.message}`, 'error');
      }
    } finally {
      set({ loadingDl: false });
    }
  },
  updateDownload: (id, patch) =>
    set(s => ({
      downloads: s.downloads.map(d => d.id === id ? { ...d, ...patch } : d),
    })),

  // Queue
  queue: [],
  fetchQueue: async () => {
    try {
      const data = await api.listQueue();
      set({ queue: data });
    } catch (error) {
      console.error('Failed to fetch queue:', error.message);
    }
  },

  // Analytics
  analytics: null,
  fetchAnalytics: async () => {
    try {
      const data = await api.getAnalytics();
      set({ analytics: data });
    } catch (error) {
      console.error('Failed to fetch analytics:', error.message);
    }
  },
  // OBS-4: backs the real daily/platform/format charts (previously
  // Math.random() on every render regardless of what was actually
  // downloaded — see backend/api/routes_logs.py's analytics_detailed()).
  analyticsDetailed: null,
  fetchAnalyticsDetailed: async () => {
    try {
      const data = await api.getAnalyticsDetailed();
      set({ analyticsDetailed: data });
    } catch (error) {
      console.error('Failed to fetch detailed analytics:', error.message);
    }
  },

  // Settings
  settings: {},
  fetchSettings: async () => {
    try {
      const data = await api.getSettings();
      set({ settings: data });
    } catch (error) {
      console.error('Failed to fetch settings:', error.message);
      get().toast('Failed to load settings', 'error');
    }
  },

  // Notifications
  toasts: [],
  toast: (message, type = "info") => {
    const id = Date.now();
    set(s => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), 4000);
  },

  // UI
  activePage: "dashboard",
  setPage:    (page) => set({ activePage: page }),
  modalOpen:  false,
  openModal:  () => set({ modalOpen: true }),
  closeModal: () => set({ modalOpen: false }),
}));
