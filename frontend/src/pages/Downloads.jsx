// src/pages/Downloads.jsx
import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { DownloadTable } from "./Dashboard";
import { Select, Button } from "../components/ui";

export default function Downloads() {
  const { downloads, fetchDownloads } = useStore();
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all" ? downloads : downloads.filter(d => d.status === filter);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Select value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="all">All status</option>
          {["downloading","queued","completed","failed","paused","cancelled"].map(s => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </Select>
        <Button onClick={() => fetchDownloads({ userInitiated: true })}>↺ Refresh</Button>
        <div className="ml-auto text-xs text-gray-600">{filtered.length} items</div>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <DownloadTable rows={filtered} showActions />
      </div>
    </div>
  );
}
