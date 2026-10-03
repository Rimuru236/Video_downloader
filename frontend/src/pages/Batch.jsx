// src/pages/Batch.jsx
import React, { useState, useRef } from "react";
import { useStore } from "../store/useStore";
import { api } from "../services/api";
import { Button, Label, Select, Textarea, Spinner } from "../components/ui";

export default function Batch() {
  const { toast, fetchDownloads, fetchQueue } = useStore();
  const [urls,    setUrls]    = useState("");
  const [quality, setQuality] = useState("bestvideo+bestaudio/best");
  const [type,    setType]    = useState("video");
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const urlList = urls.split("\n").map(u => u.trim()).filter(Boolean);

  function handleImportClick() {
    fileInputRef.current?.click();
  }

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;
    try {
      const text = await file.text();
      setUrls(prev => {
        const existing = prev.split("\n").map(u => u.trim()).filter(Boolean);
        const incoming = text.split("\n").map(u => u.trim()).filter(u => u && !u.startsWith("#"));
        return [...new Set([...existing, ...incoming])].join("\n");
      });
      toast(`Imported ${text.split("\n").filter(u => u.trim() && !u.trim().startsWith("#")).length} URLs from ${file.name}`, "success");
    } catch (err) {
      toast("Could not read file: " + err.message, "error");
    }
  }

  async function handleBatch() {
    if (!urlList.length) { toast("No URLs provided", "error"); return; }
    setLoading(true);
    try {
      const res = await api.batchDownload({ urls: urlList, quality, download_type: type, add_to_queue: true });
      toast(`Added ${res.created} downloads to queue`, "success");
      await fetchDownloads(); await fetchQueue();
      setUrls("");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div>
          <Label>URLs (one per line)</Label>
          <Textarea
            value={urls} onChange={e => setUrls(e.target.value)}
            rows={8}
            placeholder={"https://www.youtube.com/watch?v=...\nhttps://vimeo.com/...\nhttps://www.tiktok.com/..."}
          />
          <div className="text-xs text-gray-600 mt-1">{urlList.length} URL{urlList.length !== 1 ? "s" : ""} detected</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Quality</Label>
            <Select value={quality} onChange={e => setQuality(e.target.value)} className="w-full">
              <option value="bestvideo+bestaudio/best">Best available</option>
              <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
              <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
              <option value="bestaudio/best">Audio only</option>
            </Select>
          </div>
          <div>
            <Label>Type</Label>
            <Select value={type} onChange={e => setType(e.target.value)} className="w-full">
              <option value="video">Video</option>
              <option value="audio">Audio</option>
            </Select>
          </div>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileInputRef} type="file" accept=".txt,.csv,text/plain"
            onChange={handleFileChange} className="hidden"
          />
          <Button variant="default" onClick={handleImportClick}>↑ Import from file</Button>
          <Button variant="primary" onClick={handleBatch} disabled={loading || !urlList.length} className="ml-auto">
            {loading ? <Spinner /> : `Add ${urlList.length || ""} to Queue`}
          </Button>
        </div>
      </div>
    </div>
  );
}
