// src/components/Activity.jsx
import React, { useEffect, useRef, useState } from "react";
import { useStore } from "../store/useStore";
import { formatSpeed, formatBytes } from "./ui";

export default function Activity() {
  const { downloads, analytics } = useStore();
  const [speeds, setSpeeds] = useState(Array(20).fill(0));
  const canvasRef = useRef(null);

  const active    = downloads.filter(d => d.status === "downloading");
  const totalSpeed = active.reduce((s, d) => s + (d.speed || 0), 0);

  useEffect(() => {
    setSpeeds(prev => [...prev.slice(1), totalSpeed]);
  }, [totalSpeed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const max = Math.max(...speeds, 1);
    ctx.beginPath();
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 1.5;
    speeds.forEach((v, i) => {
      const x = (i / (speeds.length - 1)) * w;
      const y = h - (v / max) * (h - 4) - 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  }, [speeds]);

  const recent = downloads.slice(0, 8);

  return (
    <aside className="w-52 bg-gray-900 border-l border-gray-800 flex flex-col flex-shrink-0 overflow-hidden">
      <div className="text-xs font-medium text-gray-600 uppercase tracking-widest px-4 pt-4 pb-2 border-b border-gray-800">
        Live Activity
      </div>

      {/* Speed */}
      <div className="px-4 pt-3 pb-2 border-b border-gray-800">
        <div className="text-xs text-gray-600 uppercase tracking-wide mb-1">Total Speed</div>
        <div className="text-lg font-bold text-teal-400 font-mono">{formatSpeed(totalSpeed)}</div>
        <canvas ref={canvasRef} width={160} height={32} className="mt-2 w-full" />
      </div>

      {/* Queue mini stats */}
      <div className="px-4 py-3 border-b border-gray-800 space-y-1.5">
        <div className="text-xs text-gray-600 uppercase tracking-wide mb-2">Queue</div>
        {[
          { label: "Active",    val: downloads.filter(d => d.status === "downloading").length, color: "text-blue-400" },
          { label: "Waiting",   val: downloads.filter(d => d.status === "queued").length,      color: "text-gray-400" },
          { label: "Done",      val: downloads.filter(d => d.status === "completed").length,   color: "text-green-400" },
          { label: "Failed",    val: downloads.filter(d => d.status === "failed").length,      color: "text-red-400" },
        ].map(s => (
          <div key={s.label} className="flex justify-between text-xs">
            <span className="text-gray-500">{s.label}</span>
            <span className={`font-mono font-medium ${s.color}`}>{s.val}</span>
          </div>
        ))}
      </div>

      {/* Active downloads */}
      <div className="flex-1 overflow-y-auto">
        <div className="text-xs text-gray-600 uppercase tracking-wide px-4 pt-3 pb-2">Recent</div>
        <div className="px-3 space-y-2 pb-3">
          {recent.map(dl => (
            <div key={dl.id} className="bg-gray-800/60 rounded-lg p-2.5 border border-gray-800">
              <div className="text-xs font-medium text-gray-300 leading-tight truncate mb-1">
                {dl.title || dl.url}
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  dl.status === "downloading" ? "bg-blue-400 animate-pulse" :
                  dl.status === "completed"   ? "bg-green-400" :
                  dl.status === "failed"      ? "bg-red-400" :
                  "bg-gray-600"
                }`} />
                <span className="text-xs text-gray-600 truncate">{dl.status}</span>
                {dl.status === "downloading" && (
                  <span className="text-xs text-gray-500 ml-auto">{Math.round(dl.progress || 0)}%</span>
                )}
              </div>
              {dl.status === "downloading" && (
                <div className="mt-1.5 h-0.5 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${dl.progress || 0}%` }} />
                </div>
              )}
            </div>
          ))}
          {recent.length === 0 && (
            <div className="text-xs text-gray-700 text-center py-4">No downloads yet</div>
          )}
        </div>
      </div>
    </aside>
  );
}
