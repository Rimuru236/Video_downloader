// src/components/Sidebar.jsx
import React from "react";
import { useStore } from "../store/useStore";
import { getApiKey } from "../services/api";

const NAV = [
  { id: "dashboard",  label: "Dashboard",    icon: "⊞" },
  { id: "analytics",  label: "Analytics",    icon: "⌇" },
  { sep: true, label: "DOWNLOADS" },
  { id: "downloads",  label: "Downloads",    icon: "↓", badge: "active" },
  { id: "queue",      label: "Queue",        icon: "≡", badge: "queue" },
  { id: "batch",      label: "Batch",        icon: "⊞" },
  { sep: true, label: "CONTENT" },
  { id: "playlists",  label: "Playlists",    icon: "♪" },
  { id: "channels",   label: "Channels",     icon: "▶" },
  { id: "subtitles",  label: "Subtitles",    icon: "✎" },
  { sep: true, label: "SYSTEM" },
  { id: "settings",   label: "Settings",     icon: "⚙" },
  { id: "logs",       label: "Logs",         icon: "≡", badge: "failed" },
];

export default function Sidebar() {
  const { activePage, setPage, downloads, queue } = useStore();

  const activeCount = downloads.filter(d => d.status === "downloading").length;
  const failedCount = downloads.filter(d => d.status === "failed").length;

  const getBadge = (key) => {
    if (key === "active") return activeCount > 0 ? activeCount : null;
    if (key === "queue")  return queue.length > 0 ? queue.length : null;
    if (key === "failed") return failedCount > 0 ? failedCount : null;
    return null;
  };

  return (
    <aside className="w-48 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0">
      {/* Logo */}
      <div className="p-4 border-b border-gray-800 flex items-center gap-2">
        <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center text-white text-xs font-bold">SV</div>
        <div>
          <div className="text-sm font-bold text-white leading-tight">StreamVault</div>
          <div className="text-xs text-gray-500">Media Platform</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 overflow-y-auto">
        {NAV.map((item, i) =>
          item.sep ? (
            <div key={i} className="text-xs text-gray-600 px-2 pt-4 pb-1 tracking-widest font-medium">{item.label}</div>
          ) : (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-all relative mb-0.5
                ${activePage === item.id
                  ? "bg-indigo-600/20 text-indigo-400 font-medium"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                }`}
            >
              {activePage === item.id && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4/5 bg-indigo-500 rounded-r" />
              )}
              <span className="text-base w-4 text-center">{item.icon}</span>
              <span>{item.label}</span>
              {item.badge && getBadge(item.badge) && (
                <span className={`ml-auto text-xs font-medium px-1.5 py-0.5 rounded-full
                  ${item.badge === "failed" ? "bg-red-500/20 text-red-400" : "bg-indigo-500/20 text-indigo-400"}`}>
                  {getBadge(item.badge)}
                </span>
              )}
            </button>
          )
        )}
      </nav>

      {/* Footer — FE-4: this used to be a static "John Doe / Pro Plan",
          left over from a template and never real. There's no user-account
          model here (see SEC-1) — the actual security-relevant state a
          footer like this could honestly show is whether this browser has
          an API key configured, so show that instead of a fake identity. */}
      <button
        onClick={() => setPage("settings")}
        className="p-3 border-t border-gray-800 flex items-center gap-2 text-left hover:bg-gray-800/50 transition-colors"
        title="Go to Settings → Security"
      >
        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium text-white
          ${getApiKey() ? "bg-indigo-600" : "bg-gray-700"}`}>
          {getApiKey() ? "🔒" : "🔓"}
        </div>
        <div>
          <div className="text-xs font-medium text-gray-300">{getApiKey() ? "API key set" : "No API key"}</div>
          <div className="text-xs text-gray-600">Settings → Security</div>
        </div>
      </button>
    </aside>
  );
}
