// src/pages/Channels.jsx
import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { api } from "../services/api";
import { Button, Label, Input, Select, Spinner } from "../components/ui";

export default function Channels() {
  const { toast, fetchQueue } = useStore();
  const [url, setUrl] = useState("");
  const [max, setMax] = useState("50");
  const [after, setAfter] = useState("");
  const [quality, setQuality] = useState("bestvideo+bestaudio/best");
  const [loading, setLoading] = useState(false);

  async function start() {
    if (!url.trim()) { toast("Enter a channel URL", "error"); return; }
    setLoading(true);
    try {
      const maxVideos = parseInt(max, 10);
      await api.createDownload({
        url,
        quality,
        download_type: "channel",
        add_to_queue: true,
        playlist_end: Number.isFinite(maxVideos) && maxVideos > 0 ? maxVideos : null,
        // <input type="date"> gives "YYYY-MM-DD" — yt-dlp's dateafter wants "YYYYMMDD"
        date_after: after ? after.replaceAll("-", "") : null,
      });
      toast("Channel download queued", "success");
      await fetchQueue();
    } catch (e) { toast(e.message, "error"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div>
          <Label>Channel URL</Label>
          <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://www.youtube.com/@channelname" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Max Videos</Label>
            <Input type="number" value={max} onChange={e => setMax(e.target.value)} min={1} max={10000} />
          </div>
          <div>
            <Label>Date After</Label>
            <Input type="date" value={after} onChange={e => setAfter(e.target.value)} />
          </div>
        </div>
        <div>
          <Label>Quality</Label>
          <Select value={quality} onChange={e => setQuality(e.target.value)} className="w-full">
            <option value="bestvideo+bestaudio/best">Best available</option>
            <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
            <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
            <option value="bestaudio/best">Audio only</option>
          </Select>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-xs text-gray-500 space-y-1">
          <div>⚠ Channel downloads can be very large. Ensure you have sufficient disk space.</div>
          <div>The whole channel runs as a single queued job — its progress reflects the video currently downloading, not the channel as a whole.</div>
        </div>
        <Button variant="primary" onClick={start} disabled={loading || !url.trim()}>
          {loading ? <Spinner /> : "↓ Start Channel Download"}
        </Button>
      </div>
    </div>
  );
}
