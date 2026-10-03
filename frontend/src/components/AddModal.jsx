// src/components/AddModal.jsx
import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { api } from "../services/api";
import { Button, Input, Select, Label, Spinner } from "./ui";

export default function AddModal() {
  const { modalOpen, closeModal, fetchDownloads, fetchQueue, toast, setPage } = useStore();
  const [url,         setUrl]         = useState("");
  const [type,        setType]        = useState("video");
  const [quality,     setQuality]     = useState("bestvideo+bestaudio/best");
  const [format,      setFormat]      = useState("mp4");
  const [audioFmt,    setAudioFmt]    = useState("mp3");
  const [subtitles,   setSubtitles]   = useState(false);
  const [thumbnail,   setThumbnail]   = useState(false);
  const [metadata,    setMetadata]    = useState(true);
  const [toQueue,     setToQueue]     = useState(false);
  const [outputDir,   setOutputDir]   = useState("./downloads");
  const [loading,     setLoading]     = useState(false);
  const [meta,        setMeta]        = useState(null);
  const [fetching,    setFetching]    = useState(false);

  if (!modalOpen) return null;

  async function handleFetchMeta() {
    if (!url.trim()) return;
    setFetching(true);
    try {
      const data = await api.fetchMetadata(url);
      setMeta(data);
    } catch (e) {
      toast("Could not fetch metadata: " + e.message, "error");
    } finally {
      setFetching(false);
    }
  }

  async function handleSubmit(addToQueue) {
    if (!url.trim()) { toast("Please enter a URL", "error"); return; }
    setLoading(true);
    try {
      await api.createDownload({
        url,
        quality,
        download_type: type,
        audio_format:  type === "audio" ? audioFmt : null,
        subtitles,
        thumbnail_dl:  thumbnail,
        output_folder: outputDir,
        container_format: type !== "audio" ? format : null,
        write_metadata:   metadata,
        add_to_queue:  addToQueue,
        priority:      5,
      });
      toast(addToQueue ? "Added to queue" : "Download started!", "success");
      await fetchDownloads();
      await fetchQueue();
      handleClose();
    } catch (e) {
      toast("Error: " + e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    closeModal();
    setUrl(""); setMeta(null); setLoading(false);
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-sm font-bold text-white">Add Download</h2>
          <button onClick={handleClose} aria-label="Close" className="text-gray-500 hover:text-gray-300 text-lg leading-none">✕</button>
        </div>

        <div className="p-5 space-y-4">
          {/* URL */}
          <div>
            <Label>URL</Label>
            <div className="flex gap-2">
              <Input
                value={url} onChange={e => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="flex-1"
              />
              <Button onClick={handleFetchMeta} disabled={fetching} variant="default">
                {fetching ? <Spinner /> : "Preview"}
              </Button>
            </div>
          </div>

          {/* Metadata preview */}
          {meta && (
            <div className="bg-gray-800 rounded-lg p-3 flex gap-3">
              {meta.thumbnail && (
                <img src={meta.thumbnail} alt="" className="w-16 h-10 object-cover rounded" />
              )}
              <div className="min-w-0">
                <div className="text-xs font-medium text-gray-200 truncate">{meta.title}</div>
                <div className="text-xs text-gray-500 mt-0.5">{meta.uploader} · {meta.extractor}</div>
                {meta.type === "playlist" && (
                  <div className="text-xs text-indigo-400 mt-0.5">{meta.entry_count} videos</div>
                )}
              </div>
            </div>
          )}

          {/* Type toggle */}
          <div>
            <Label>Type</Label>
            <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
              {["video","audio","playlist"].map(t => (
                <button
                  key={t}
                  onClick={() => setType(t)}
                  className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all capitalize
                    ${type === t ? "bg-gray-700 text-white" : "text-gray-500 hover:text-gray-300"}`}
                >
                  {t}
                </button>
              ))}
            </div>
            {/* FE-3: Channel and Subtitle are deliberately not tabs here — each
                needs its own fields (channel URL + max videos + date filter;
                subtitle language/format/auto-caption), which don't fit this
                single-URL quick-add flow. Point at the dedicated pages that
                already have the right UI for them, rather than silently
                omitting the options with no explanation. */}
            <div className="text-xs text-gray-600 mt-1.5">
              Need a channel or subtitles-only download?{" "}
              <button
                type="button"
                onClick={() => { closeModal(); setPage(type === "playlist" ? "channels" : "subtitles"); }}
                className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2"
              >
                Use Channels / Subtitles
              </button>
            </div>
          </div>

          {/* Quality & Format */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Quality</Label>
              <Select value={quality} onChange={e => setQuality(e.target.value)} className="w-full">
                <option value="bestvideo+bestaudio/best">Best available</option>
                <option value="bestvideo[height<=2160]+bestaudio/best">4K (2160p)</option>
                <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
                <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
                <option value="bestvideo[height<=480]+bestaudio/best">480p</option>
                <option value="bestaudio/best">Audio only</option>
              </Select>
            </div>
            {type === "audio" ? (
              <div>
                <Label>Audio Format</Label>
                <Select value={audioFmt} onChange={e => setAudioFmt(e.target.value)} className="w-full">
                  {["mp3","aac","flac","ogg","opus","wav"].map(f => (
                    <option key={f} value={f}>{f.toUpperCase()}</option>
                  ))}
                </Select>
              </div>
            ) : (
              <div>
                <Label>Container</Label>
                <Select value={format} onChange={e => setFormat(e.target.value)} className="w-full">
                  {["mp4","mkv","webm"].map(f => (
                    <option key={f} value={f}>{f.toUpperCase()}</option>
                  ))}
                </Select>
              </div>
            )}
          </div>

          {/* Options */}
          <div className="flex flex-wrap gap-4">
            {[
              { label: "Subtitles",  val: subtitles, set: setSubtitles },
              { label: "Thumbnail",  val: thumbnail, set: setThumbnail },
              { label: "Metadata",   val: metadata,  set: setMetadata  },
            ].map(o => (
              <label key={o.label} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox" checked={o.val} onChange={e => o.set(e.target.checked)}
                  className="w-3.5 h-3.5 accent-indigo-500"
                />
                <span className="text-xs text-gray-400">{o.label}</span>
              </label>
            ))}
          </div>

          {/* Output folder */}
          <div>
            <Label>Output Folder</Label>
            <Input value={outputDir} onChange={e => setOutputDir(e.target.value)} />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-2 justify-end px-5 py-4 border-t border-gray-800">
          <Button onClick={handleClose} variant="ghost">Cancel</Button>
          <Button onClick={() => handleSubmit(true)} variant="default" disabled={loading}>
            Add to Queue
          </Button>
          <Button onClick={() => handleSubmit(false)} variant="primary" disabled={loading}>
            {loading ? <Spinner /> : "Download Now"}
          </Button>
        </div>
      </div>
    </div>
  );
}
