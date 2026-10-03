// src/pages/Logs.jsx
import React, { useState, useEffect, useRef } from "react";
import { api } from "../services/api";
import { Button, Input, Select, Spinner } from "../components/ui";

const LEVEL_STYLE = {
  INFO:  "text-blue-400",
  OK:    "text-green-400",
  ERROR: "text-red-400",
  WARN:  "text-amber-400",
};

export default function Logs() {
  const [lines,   setLines]   = useState([]);
  const [filter,  setFilter]  = useState("all");
  const [search,  setSearch]  = useState("");
  const [loading, setLoading] = useState(false);
  const [raw,     setRaw]     = useState(false);
  const [rawText, setRawText] = useState("");
  const endRef = useRef(null);

  useEffect(() => { load(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView(); }, [lines]);

  async function load() {
    setLoading(true);
    try {
      const params = filter !== "all" ? `level=${filter}` : "";
      const data = await api.getLogs(params);
      setLines(data);
    } catch (e) {
      // fallback to raw log file
      const text = await api.getLogFile().catch(() => "No logs available");
      setRaw(true);
      setRawText(text);
    } finally {
      setLoading(false);
    }
  }

  async function exportLogs() {
    const text = await api.exportLogs();
    const blob = new Blob([text], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "streamvault.log";
    a.click();
  }

  const filtered = lines.filter(l => {
    if (filter !== "all" && l.level !== filter) return false;
    if (search && !l.message?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search logs…" className="max-w-xs" />
        <Select value={filter} onChange={e => { setFilter(e.target.value); }}>
          <option value="all">All levels</option>
          <option value="INFO">INFO</option>
          <option value="OK">OK</option>
          <option value="WARN">WARN</option>
          <option value="ERROR">ERROR</option>
        </Select>
        <Button onClick={load}>{loading ? <Spinner /> : "↺ Refresh"}</Button>
        <Button onClick={exportLogs} className="ml-auto">↓ Export</Button>
      </div>

      <div className="bg-[#0d1117] rounded-xl border border-gray-800 p-4 h-[520px] overflow-y-auto font-mono text-xs leading-relaxed">
        {raw ? (
          <pre className="text-gray-400 whitespace-pre-wrap">{rawText}</pre>
        ) : filtered.length === 0 ? (
          <div className="text-gray-700 text-center py-16">No log entries found</div>
        ) : (
          filtered.map(l => (
            <div key={l.id} className="py-0.5 hover:bg-white/5 px-1 rounded">
              <span className="text-gray-600">{l.created_at?.replace("T"," ").split(".")[0]}</span>
              {" "}
              <span className={`${LEVEL_STYLE[l.level] || "text-gray-400"} font-medium`}>[{l.level}]</span>
              {" "}
              <span className="text-gray-300">{l.message}</span>
              {l.download_id && (
                <span className="text-indigo-500 ml-1">[{l.download_id.slice(0,8)}]</span>
              )}
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>

      <div className="text-xs text-gray-700">{filtered.length} entries shown</div>
    </div>
  );
}
