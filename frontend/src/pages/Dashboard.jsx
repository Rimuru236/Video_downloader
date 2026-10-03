// src/pages/Dashboard.jsx
import React, { useEffect, useRef } from "react";
import { useStore } from "../store/useStore";
import { api, openDownloadedFile } from "../services/api";
import { MetricCard, StatusPill, ProgressBar, formatSpeed, formatETA, formatBytes } from "../components/ui";

export default function Dashboard() {
  const { downloads, analytics, fetchDownloads, analyticsDetailed, fetchAnalyticsDetailed } = useStore();
  const speedRef = useRef(null);
  const siteRef  = useRef(null);
  const chartsRef = useRef({});
  // OBS-4: rolling buffer of the real avgSpeed value, sampled every time
  // `downloads` refreshes (App.jsx polls it) — replaces a Math.random()
  // sparkline that was seeded once and never touched real data again.
  const speedHistoryRef = useRef([]);

  const active    = downloads.filter(d => d.status === "downloading").length;
  const completed = downloads.filter(d => d.status === "completed").length;
  const failed    = downloads.filter(d => d.status === "failed").length;
  const avgSpeed  = downloads
    .filter(d => d.status === "downloading" && d.speed)
    .reduce((a, d, _, arr) => a + d.speed / arr.length, 0);

  useEffect(() => {
    fetchAnalyticsDetailed();
  }, []);

  useEffect(() => {
    // Poll until Chart.js is available (loaded via index.html script tag)
    const id = setInterval(() => {
      if (window.Chart) { clearInterval(id); initCharts(); }
    }, 500); // Increased from 100ms to 500ms to reduce CPU usage
    return () => clearInterval(id);
  }, []);

  // Push a fresh real sample into the speed chart whenever avgSpeed changes
  // (i.e. whenever the periodic downloads poll refreshes it), instead of
  // ever regenerating fake data.
  useEffect(() => {
    const kbps = Math.round((avgSpeed || 0) / 1024);
    const hist = speedHistoryRef.current;
    hist.push(kbps);
    if (hist.length > 30) hist.shift();
    const chart = chartsRef.current.speed;
    if (chart) {
      chart.data.labels = hist.map((_, i) => i);
      chart.data.datasets[0].data = [...hist];
      chart.update("none");
    }
  }, [avgSpeed]);

  // Rebuild the platform donut whenever real analytics data arrives.
  useEffect(() => {
    const chart = chartsRef.current.site;
    if (!chart || !analyticsDetailed) return;
    const platforms = analyticsDetailed.platforms.slice(0, 5);
    const shown = platforms.length ? platforms : [{ site: "No data yet", count: 1 }];
    chart.data.labels = shown.map(p => p.site);
    chart.data.datasets[0].data = shown.map(p => p.count);
    chart.update();
  }, [analyticsDetailed]);

  function initCharts() {
    const Chart = window.Chart;

    // Speed chart — starts with whatever's already in the rolling buffer
    // (empty on first mount; initCharts only runs once Chart.js has
    // loaded, by which point the avgSpeed effect above may already have
    // pushed a sample or two).
    if (speedRef.current && !chartsRef.current.speed) {
      const pts = speedHistoryRef.current.length ? speedHistoryRef.current : [Math.round((avgSpeed || 0) / 1024)];
      chartsRef.current.speed = new Chart(speedRef.current, {
        type: "line",
        data: {
          labels: pts.map((_, i) => i),
          datasets: [{
            data: pts, borderColor: "#6366f1", borderWidth: 2,
            fill: true, backgroundColor: "rgba(99,102,241,0.08)",
            tension: 0.4, pointRadius: 0,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { display: false },
            y: { display: true, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#555", font: { size: 10 }, callback: v => `${v}K` }, min: 0 },
          },
        },
      });
    }

    // Site donut — real platform breakdown once analyticsDetailed has loaded
    if (siteRef.current && !chartsRef.current.site) {
      const platforms = analyticsDetailed?.platforms?.slice(0, 5) || [];
      const shown = platforms.length ? platforms : [{ site: "No data yet", count: 1 }];
      chartsRef.current.site = new Chart(siteRef.current, {
        type: "doughnut",
        data: {
          labels: shown.map(p => p.site),
          datasets: [{ data: shown.map(p => p.count), backgroundColor: ["#ef4444","#22d3ee","#18181b","#ff5500","#6366f1"], borderWidth: 0 }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "right", labels: { color: "#888", font: { size: 11 }, boxWidth: 10, padding: 8 } } },
          cutout: "62%",
        },
      });
    }
  }

  const recent = downloads.slice(0, 10);

  return (
    <div className="space-y-5">
      {/* Metrics */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Active Downloads" value={active}  color="text-blue-400"  sub={`${active} thread${active !== 1 ? "s" : ""}`} />
        <MetricCard label="Completed Today"  value={completed} color="text-green-400" sub={analytics ? `${formatBytes(analytics.total_bytes)} total` : "—"} />
        <MetricCard label="Failed"           value={failed}  color="text-red-400"   sub={failed > 0 ? "needs attention" : "none"} />
        <MetricCard label="Avg Speed"        value={formatSpeed(avgSpeed).split("/")[0]} color="text-indigo-400" sub={formatSpeed(avgSpeed)} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex justify-between mb-3">
            <span className="text-xs font-medium text-gray-300">Download Speed</span>
            <span className="text-xs text-gray-600">Live</span>
          </div>
          <div className="relative h-36">
            <canvas ref={speedRef} />
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-300 mb-3">Source Breakdown</div>
          <div className="relative h-36">
            <canvas ref={siteRef} />
          </div>
        </div>
      </div>

      {/* Downloads table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <span className="text-xs font-medium text-gray-300">Recent Downloads</span>
          <span className="text-xs text-gray-600">Last 24h</span>
        </div>
        <DownloadTable rows={recent} />
      </div>
    </div>
  );
}

export function DownloadTable({ rows, showActions = false }) {
  const { toast, fetchDownloads } = useStore();

  async function act(fn, msg) {
    try { await fn(); toast(msg, "success"); await fetchDownloads({ userInitiated: true }); }
    catch (e) { toast(e.message, "error"); }
  }

  async function openFile(id) {
    try { await openDownloadedFile(id); }
    catch (e) { toast(e.message, "error"); }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-600 uppercase tracking-wide border-b border-gray-800">
            {["Status","Title","Source","Res","Size","Progress","Speed","ETA",""].map(h => (
              <th key={h} className="text-left px-4 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(dl => (
            <tr key={dl.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
              <td className="px-4 py-2.5"><StatusPill status={dl.status} /></td>
              <td className="px-4 py-2.5 max-w-[180px]">
                <div className="truncate text-gray-200 font-medium">{dl.title || dl.url}</div>
              </td>
              <td className="px-4 py-2.5 text-gray-500">{dl.source_site || "—"}</td>
              <td className="px-4 py-2.5 font-mono text-gray-500">{dl.resolution || "—"}</td>
              <td className="px-4 py-2.5 text-gray-500">{formatBytes(dl.filesize)}</td>
              <td className="px-4 py-2.5">
                <ProgressBar value={dl.progress || 0} status={dl.status} />
              </td>
              <td className="px-4 py-2.5 font-mono text-gray-500">{formatSpeed(dl.speed)}</td>
              <td className="px-4 py-2.5 text-gray-500">{formatETA(dl.eta)}</td>
              <td className="px-4 py-2.5">
                <div className="flex gap-1">
                  {dl.status === "downloading" && <>
                    <ActionBtn onClick={() => act(() => api.pauseDownload(dl.id), "Paused")} title="Pause">⏸</ActionBtn>
                    <ActionBtn onClick={() => act(() => api.cancelDownload(dl.id), "Cancelled")} title="Cancel">✕</ActionBtn>
                  </>}
                  {dl.status === "paused" && (
                    <ActionBtn onClick={() => act(() => api.resumeDownload(dl.id), "Resumed")} title="Resume">▶</ActionBtn>
                  )}
                  {dl.status === "failed" && (
                    <ActionBtn onClick={() => act(() => api.retryDownload(dl.id), "Retrying...")} title="Retry">↺</ActionBtn>
                  )}
                  {dl.status === "completed" && (
                    <ActionBtn onClick={() => openFile(dl.id)} title="Open file">↗</ActionBtn>
                  )}
                </div>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={9} className="text-center py-10 text-gray-700 text-xs">No downloads yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ActionBtn({ onClick, title, children }) {
  return (
    <button
      onClick={onClick} title={title} aria-label={title}
      className="w-6 h-6 rounded flex items-center justify-center text-gray-600 hover:text-gray-300 hover:bg-gray-700 border border-gray-800 text-xs transition-colors"
    >
      {children}
    </button>
  );
}
