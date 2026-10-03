// src/components/ui.jsx — shared primitives
import React from "react";

export function StatusPill({ status }) {
  const map = {
    downloading: "bg-blue-500/15 text-blue-400",
    completed:   "bg-green-500/15 text-green-400",
    queued:      "bg-gray-500/15 text-gray-400",
    failed:      "bg-red-500/15 text-red-400",
    paused:      "bg-amber-500/15 text-amber-400",
    cancelled:   "bg-gray-600/15 text-gray-500",
    pending:     "bg-purple-500/15 text-purple-400",
    processing:  "bg-cyan-500/15 text-cyan-400",
  };
  const icons = {
    downloading: "⬇", completed: "✓", queued: "○",
    failed: "✕", paused: "⏸", cancelled: "✕", pending: "…", processing: "⟳",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || "bg-gray-700 text-gray-400"}`}>
      {icons[status]} {status}
    </span>
  );
}

export function ProgressBar({ value, status }) {
  const color = status === "completed" ? "bg-green-500"
    : status === "failed" ? "bg-red-500"
    : status === "paused" ? "bg-amber-500"
    : "bg-indigo-500";
  return (
    // FE-5: status here was color-only (green/red/amber/indigo) with no
    // text equivalent — invisible to a screen reader and indistinguishable
    // to anyone with red/green color vision deficiency. role="progressbar"
    // + the value/label attributes give it a real accessible name.
    <div
      className="h-1 w-20 bg-gray-800 rounded-full overflow-hidden"
      role="progressbar"
      aria-valuenow={Math.round(value || 0)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${status || "unknown"}, ${Math.round(value || 0)}%`}
    >
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${value}%` }} />
    </div>
  );
}

export function Card({ children, className = "" }) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl ${className}`}>
      {children}
    </div>
  );
}

export function MetricCard({ label, value, sub, color = "text-white" }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-500 mb-1.5">{label}</div>
      <div className={`text-2xl font-bold leading-none ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  );
}

export function Button({ children, onClick, variant = "default", size = "sm", className = "" }) {
  const base = "inline-flex items-center gap-1.5 rounded-md font-medium transition-colors cursor-pointer";
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm" };
  const variants = {
    default:  "border border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800",
    primary:  "bg-indigo-600 text-white hover:bg-indigo-500 border-0",
    danger:   "bg-red-600/20 text-red-400 border border-red-700/50 hover:bg-red-600/30",
    ghost:    "text-gray-400 hover:text-gray-200 hover:bg-gray-800 border-0",
  };
  return (
    <button onClick={onClick} className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}>
      {children}
    </button>
  );
}

export function IconButton({ onClick, title, children }) {
  return (
    <button
      onClick={onClick} title={title} aria-label={title}
      className="w-7 h-7 rounded-md flex items-center justify-center text-gray-500 hover:text-gray-200 hover:bg-gray-800 border border-gray-800 transition-colors text-xs"
    >
      {children}
    </button>
  );
}

export function Input({ className = "", ...props }) {
  return (
    <input
      className={`w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500 transition-colors ${className}`}
      {...props}
    />
  );
}

export function Select({ className = "", children, ...props }) {
  return (
    <select
      className={`bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500 transition-colors ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}

export function Label({ children, className = "" }) {
  return <div className={`text-xs text-gray-500 font-medium mb-1.5 tracking-wide uppercase ${className}`}>{children}</div>;
}

export function Textarea({ className = "", ...props }) {
  return (
    <textarea
      className={`w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500 resize-vertical font-mono transition-colors ${className}`}
      {...props}
    />
  );
}

export function Spinner() {
  return <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />;
}

export function SectionHeader({ title, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-sm font-semibold text-gray-200">{title}</h2>
      {action}
    </div>
  );
}

export function formatBytes(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatSpeed(bps) {
  if (!bps) return "—";
  return formatBytes(bps) + "/s";
}

export function formatETA(secs) {
  if (!secs) return "—";
  if (secs < 60)   return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs/60)}m ${secs%60}s`;
  return `${Math.floor(secs/3600)}h ${Math.floor((secs%3600)/60)}m`;
}
