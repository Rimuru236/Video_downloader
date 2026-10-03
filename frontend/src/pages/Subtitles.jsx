// src/pages/Subtitles.jsx
import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { api } from "../services/api";
import { Button, Label, Input, Select, Spinner } from "../components/ui";

const LANGS = [
  ["en","English"],["fr","French"],["es","Spanish"],["de","German"],
  ["ja","Japanese"],["zh","Chinese"],["ar","Arabic"],["pt","Portuguese"],
  ["ru","Russian"],["ko","Korean"],["it","Italian"],["nl","Dutch"],
];

export default function Subtitles() {
  const { toast } = useStore();
  const [url, setUrl]       = useState("");
  const [isPlaylist, setIsPlaylist] = useState(false);
  const [maxVideos, setMaxVideos]   = useState("50");
  const [langs, setLangs]   = useState(new Set(["en"]));
  const [fmt, setFmt]       = useState("srt");
  const [auto, setAuto]     = useState(true);
  // "separate": subtitle files only, no video. "embed": soft/switchable track
  // muxed into the video. "hardsub": burned into the video frame (re-encode).
  const [mode, setMode]     = useState("embed");
  const [loading, setLoading] = useState(false);
  const [meta, setMeta]     = useState(null);
  const [fetching, setFetching] = useState(false);

  // Merge "en" (manual) and "en (auto)" entries from metadata into one map:
  // code -> { manual: bool, auto: bool }. This is the authoritative source
  // once a single video's metadata has been fetched (doesn't apply in
  // playlist/channel mode — there's no single subtitle track list to check).
  const rawSubs = meta?.subtitles || {};
  const availMap = {};
  for (const key of Object.keys(rawSubs)) {
    const isAuto = key.endsWith(" (auto)");
    const code = isAuto ? key.replace(" (auto)", "") : key;
    availMap[code] = availMap[code] || { manual: false, auto: false };
    if (isAuto) availMap[code].auto = true; else availMap[code].manual = true;
  }
  const availCodes = Object.keys(availMap).sort();
  const verified = meta?.type === "video"; // metadata fetched for a single video, so availCodes is authoritative

  function toggleLang(code) {
    setLangs(prev => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  async function fetchInfo() {
    if (!url.trim()) return;
    setFetching(true);
    try {
      const data = await api.fetchMetadata(url);
      setMeta(data);
      const codes = new Set(Object.keys(data.subtitles || {}).map(k => k.replace(" (auto)", "")));
      if (codes.size > 0) {
        const kept = [...langs].filter(c => codes.has(c));
        setLangs(new Set(kept.length ? kept : [codes.has("en") ? "en" : [...codes][0]]));
      }
    } catch (e) { toast(e.message, "error"); }
    finally { setFetching(false); }
  }

  async function download() {
    if (!url.trim()) { toast("Enter a URL", "error"); return; }
    if (langs.size === 0) { toast("Select at least one subtitle language", "error"); return; }

    // Pre-flight: once metadata is known, the picker only ever offers codes
    // that actually exist, so there's nothing left to validate against — but
    // a language available *only* as an auto-generated caption requires the
    // "Auto-generated" toggle to be on, or yt-dlp will silently skip it.
    let finalAuto = auto;
    if (verified) {
      const needsAuto = [...langs].some(c => availMap[c] && !availMap[c].manual);
      if (needsAuto && !auto) {
        finalAuto = true;
        toast("Enabled auto-generated captions — required for the selected language(s)", "info");
      }
    }

    const embed_subtitles = mode === "embed";
    const hardsub         = mode === "hardsub";

    setLoading(true);
    try {
      if (isPlaylist) {
        const res = await api.batchSubtitleDownload({
          url,
          subtitle_langs:  [...langs].join(","),
          subtitle_format: fmt,
          subtitle_auto:   finalAuto,
          embed_subtitles,
          hardsub,
          limit: parseInt(maxVideos, 10) || undefined,
        });
        toast(
          `Queued subtitles for ${res.created} video${res.created !== 1 ? "s" : ""}`
          + (res.truncated ? ` (capped at ${res.created} of ${res.total_available})` : ""),
          "success"
        );
      } else {
        await api.createDownload({
          url,
          download_type:   "subtitle",
          subtitles:       true,
          subtitle_langs:  [...langs].join(","),
          subtitle_format: fmt,
          subtitle_auto:   finalAuto,
          embed_subtitles,
          hardsub,
          add_to_queue:    false,
        });
        toast(hardsub ? "Subtitle burn-in started (this re-encodes the video, may take a while)" : "Subtitle download started", "success");
      }
    } catch (e) { toast(e.message, "error"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div>
          <Label>{isPlaylist ? "Playlist / Channel URL" : "Video URL"}</Label>
          <div className="flex gap-2">
            <Input
              value={url} onChange={e => { setUrl(e.target.value); setMeta(null); }}
              placeholder={isPlaylist ? "https://www.youtube.com/@channel or /playlist?list=..." : "https://..."}
              className="flex-1"
            />
            <Button onClick={fetchInfo} disabled={fetching}>{fetching ? <Spinner /> : "Check"}</Button>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer mt-2">
            <input
              type="checkbox" checked={isPlaylist}
              onChange={e => { setIsPlaylist(e.target.checked); setMeta(null); }}
              className="accent-indigo-500"
            />
            This is a playlist or channel URL (fetch subtitles for every video)
          </label>
        </div>

        {isPlaylist && (
          <div>
            <Label>Max Videos <span className="normal-case text-gray-600">(safety cap for large channels)</span></Label>
            <Input type="number" value={maxVideos} onChange={e => setMaxVideos(e.target.value)} min={1} max={2000} className="w-32" />
          </div>
        )}

        {isPlaylist && meta?.type === "playlist" && (
          <div className="text-xs text-gray-500">
            <span className="text-gray-300 font-medium">{meta.title}</span> — {meta.entry_count} video{meta.entry_count !== 1 ? "s" : ""} found
            {meta.entry_count > parseInt(maxVideos, 10) && (
              <span className="text-amber-400"> (only the first {maxVideos} will be queued)</span>
            )}
          </div>
        )}

        {!isPlaylist && verified && availCodes.length > 0 && (
          <div className="bg-gray-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-gray-500">Available subtitles ({availCodes.length}) — click to select</div>
              <button
                onClick={() => setLangs(new Set(langs.size === availCodes.length ? [] : availCodes))}
                className="text-xs text-indigo-400 hover:text-indigo-300"
              >
                {langs.size === availCodes.length ? "Deselect all" : "Select all"}
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {availCodes.map(code => {
                const info = availMap[code];
                const active = langs.has(code);
                return (
                  <span
                    key={code}
                    onClick={() => toggleLang(code)}
                    className={`text-xs px-2 py-0.5 rounded-full cursor-pointer transition-colors border
                      ${active
                        ? (info.manual ? "bg-indigo-500/25 text-indigo-300 border-indigo-500/50" : "bg-amber-500/25 text-amber-300 border-amber-500/50")
                        : "bg-gray-900 text-gray-500 border-gray-700 hover:text-gray-300"}`}
                  >
                    {code}{!info.manual && " (auto)"}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {!isPlaylist && verified && availCodes.length === 0 && (
          <div className="text-xs text-gray-600">No subtitles found for this video.</div>
        )}

        {(isPlaylist || !verified) && (
          <div>
            <Label>Language <span className="normal-case text-gray-600">(unverified — click "Check" to confirm availability)</span></Label>
            <div className="flex flex-wrap gap-1">
              {LANGS.map(([code, name]) => {
                const active = langs.has(code);
                return (
                  <span
                    key={code}
                    onClick={() => toggleLang(code)}
                    title={name}
                    className={`text-xs px-2 py-0.5 rounded-full cursor-pointer transition-colors border
                      ${active ? "bg-indigo-500/25 text-indigo-300 border-indigo-500/50" : "bg-gray-800 text-gray-500 border-gray-700 hover:text-gray-300"}`}
                  >
                    {code}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        <div>
          <Label>Format</Label>
          <Select value={fmt} onChange={e => setFmt(e.target.value)} className="w-full">
            {["srt","vtt","ass","lrc"].map(f => <option key={f} value={f}>{f.toUpperCase()}</option>)}
          </Select>
        </div>

        <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
          <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} className="accent-indigo-500" /> Auto-generated
        </label>

        <div>
          <Label>Subtitle handling</Label>
          <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
            {[
              { id: "separate", label: "Files only",  hint: "Just the subtitle file(s), no video" },
              { id: "embed",    label: "Soft embed",   hint: "Switchable track muxed into the video" },
              { id: "hardsub",  label: "Burn in",      hint: "Permanently rendered into the frame (re-encode, slower)" },
            ].map(o => (
              <button
                key={o.id}
                type="button"
                onClick={() => setMode(o.id)}
                title={o.hint}
                className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all
                  ${mode === o.id ? "bg-gray-700 text-white" : "text-gray-500 hover:text-gray-300"}`}
              >
                {o.label}
              </button>
            ))}
          </div>
          {mode === "hardsub" && (
            <div className="text-xs text-amber-400 mt-1.5">Burning in re-encodes the whole video — this is much slower than embedding.</div>
          )}
        </div>

        <Button variant="primary" onClick={download} disabled={loading || !url.trim()}>
          {loading ? <Spinner /> : "↓ Download Subtitles"}
        </Button>
      </div>
    </div>
  );
}
