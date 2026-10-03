// src/App.jsx
import React, { useEffect } from "react";
import Sidebar    from "./components/Sidebar";
import Topbar     from "./components/Topbar";
import Activity   from "./components/Activity";
import AddModal   from "./components/AddModal";
import Toasts     from "./components/Toasts";
import { useStore } from "./store/useStore";

import Dashboard  from "./pages/Dashboard";
import Downloads  from "./pages/Downloads";
import Queue      from "./pages/Queue";
import Analytics  from "./pages/Analytics";
import Batch      from "./pages/Batch";
import Playlists  from "./pages/Playlists";
import Channels   from "./pages/Channels";
import Subtitles  from "./pages/Subtitles";
import Settings   from "./pages/Settings";
import Logs       from "./pages/Logs";

const PAGE_MAP = {
  dashboard: Dashboard,
  downloads: Downloads,
  queue:     Queue,
  analytics: Analytics,
  batch:     Batch,
  playlists: Playlists,
  channels:  Channels,
  subtitles: Subtitles,
  settings:  Settings,
  logs:      Logs,
};

export default function App() {
  const { activePage, fetchDownloads, fetchQueue, fetchAnalytics } = useStore();

  useEffect(() => {
    fetchDownloads();
    fetchQueue();
    fetchAnalytics();
    // Use configurable polling interval (default 15s, can be overridden via VITE_POLL_INTERVAL)
    const pollInterval = parseInt(import.meta.env.VITE_POLL_INTERVAL || "15000");
    const interval = setInterval(() => {
      fetchDownloads();
      fetchQueue();
    }, pollInterval);
    return () => clearInterval(interval);
  }, []);

  const PageComponent = PAGE_MAP[activePage] || Dashboard;

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-5 bg-gray-950">
          <PageComponent />
        </main>
      </div>
      <Activity />
      <AddModal />
      <Toasts />
    </div>
  );
}
