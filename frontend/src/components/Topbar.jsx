// src/components/Topbar.jsx
import React from "react";
import { useStore } from "../store/useStore";

const TITLES = {
  dashboard: "Dashboard", downloads: "Downloads", queue: "Queue Manager",
  analytics: "Analytics", batch: "Batch Downloader", playlists: "Playlist Manager",
  channels: "Channel Downloader", subtitles: "Subtitle Manager",
  settings: "Settings", logs: "Logs",
};

export default function Topbar() {
  const { activePage, openModal } = useStore();
  return (
    <header className="h-13 bg-gray-900 border-b border-gray-800 px-5 flex items-center gap-3 flex-shrink-0">
      <h1 className="text-sm font-bold text-white">{TITLES[activePage] || activePage}</h1>
      <div className="flex-1" />
      <button
        onClick={openModal}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-gray-700 text-gray-300 hover:bg-gray-800 transition-colors"
      >
        + Add URL
      </button>
      <button
        onClick={openModal}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-500 transition-colors"
      >
        ↓ Download Now
      </button>
    </header>
  );
}
