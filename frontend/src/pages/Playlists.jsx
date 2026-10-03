// src/pages/Playlists.jsx
import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { api } from "../services/api";
import { Button, Label, Input, Select, Spinner } from "../components/ui";
import { formatBytes } from "../components/ui";

export default function Playlists() {
  const { toast, fetchDownloads, fetchQueue } = useStore();
  const [url, setUrl] = useState("");
  const [quality, setQuality] = useState("bestvideo+bestaudio/best");
  const [range, setRange] = useState("");
  const [subs, setSubs] = useState(true);
  const [thumbs, setThumbs] = useState(false);
  const [loading, setLoading] = useState(false);
  const [meta, setMeta] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [selected, setSelected] = useState(new Set());

  async function fetchPlaylist() {
    if (!url.trim()) return;
    setFetching(true);
    try {
      const data = await api.fetchMetadata(url);
      setMeta(data);
      if (data.entries) setSelected(new Set(data.entries.map(e => e.id)));
    } catch (e) { toast(e.message, "error"); }
    finally { setFetching(false); }
  }

  async function startDownload() {
    setLoading(true);
    try {
      // Explicit "Range" text (e.g. "1-50") wins — it's already in yt-dlp's
      // own playlist_items syntax. Otherwise, if the user deselected any
      // videos from the fetched preview, translate the remaining selection
      // into 1-based positions (the preview list is in playlist order, capped
      // at 100 entries — see metadata_service._fetch). If everything is
      // selected (or nothing was fetched to select from), leave playlist_items
      // unset so the whole playlist downloads.
      let playlistItems = range.trim() || null;
      if (!playlistItems && meta?.entries?.length && selected.size < meta.entries.length) {
        playlistItems = meta.entries
          .map((e, i) => (selected.has(e.id) ? i + 1 : null))
          .filter(Boolean)
          .join(",");
      }
      await api.createDownload({
        url, quality, download_type: "playlist",
        subtitles: subs, thumbnail_dl: thumbs,
        playlist_items: playlistItems,
        add_to_queue: true,
      });
      toast("Playlist added to queue", "success");
      await fetchQueue();
    } catch (e) { toast(e.message, "error"); }
    finally { setLoading(false); }
  }

  const toggleAll = () => {
    if (!meta?.entries) return;
    setSelected(selected.size === meta.entries.length ? new Set() : new Set(meta.entries.map(e => e.id)));
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div>
          <Label>Playlist URL</Label>
          <div className="flex gap-2">
            <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://www.youtube.com/playlist?list=..." className="flex-1" />
            <Button onClick={fetchPlaylist} disabled={fetching}>{fetching ? <Spinner /> : "Fetch"}</Button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Quality</Label>
            <Select value={quality} onChange={e => setQuality(e.target.value)} className="w-full">
              <option value="bestvideo+bestaudio/best">Best</option>
              <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
              <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
              <option value="bestaudio/best">Audio only</option>
            </Select>
          </div>
          <div>
            <Label>Range (e.g. 1-50)</Label>
            <Input value={range} onChange={e => setRange(e.target.value)} placeholder="1-50 (leave blank for all)" />
          </div>
        </div>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
            <input type="checkbox" checked={subs} onChange={e => setSubs(e.target.checked)} className="accent-indigo-500" /> Subtitles
          </label>
          <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
            <input type="checkbox" checked={thumbs} onChange={e => setThumbs(e.target.checked)} className="accent-indigo-500" /> Thumbnails
          </label>
        </div>

        {meta && (
          <div className="bg-gray-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-xs font-medium text-gray-200">{meta.title}</div>
                <div className="text-xs text-gray-500">{meta.uploader} · {meta.entry_count} videos</div>
              </div>
              <button onClick={toggleAll} className="text-xs text-indigo-400 hover:text-indigo-300">
                {selected.size === (meta.entries?.length || 0) ? "Deselect all" : "Select all"}
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {(meta.entries || []).map((e, i) => (
                <label key={e.id} className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer hover:text-gray-200 py-0.5">
                  <input type="checkbox" checked={selected.has(e.id)}
                    onChange={() => { const s = new Set(selected); s.has(e.id) ? s.delete(e.id) : s.add(e.id); setSelected(s); }}
                    className="accent-indigo-500" />
                  <span className="text-gray-600 w-5">{i+1}.</span>
                  <span className="truncate">{e.title}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <Button variant="primary" onClick={startDownload} disabled={loading || !url.trim()}>
          {loading ? <Spinner /> : "↓ Download Playlist"}
        </Button>
      </div>
    </div>
  );
}
