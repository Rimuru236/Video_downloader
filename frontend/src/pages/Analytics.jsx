// src/pages/Analytics.jsx
import React, { useEffect, useRef } from "react";
import { useStore } from "../store/useStore";
import { MetricCard, formatBytes, formatSpeed } from "../components/ui";

export default function Analytics() {
  const { analytics, fetchAnalytics, analyticsDetailed, fetchAnalyticsDetailed } = useStore();
  const dailyRef   = useRef(null);
  const dataRef    = useRef(null);
  const platformRef = useRef(null);
  const formatRef  = useRef(null);
  const charts     = useRef({});

  useEffect(() => {
    fetchAnalytics();
    fetchAnalyticsDetailed();
  }, []);

  // OBS-4: charts are (re)built once Chart.js has loaded AND the real data
  // has arrived — this used to build once with Math.random() and never
  // touch the charts again, regardless of what the app was actually doing.
  useEffect(() => {
    if (!analyticsDetailed) return;
    const id = setInterval(() => {
      if (window.Chart) { clearInterval(id); initCharts(analyticsDetailed); }
    }, 300);
    return () => clearInterval(id);
  }, [analyticsDetailed]);

  function initCharts(data) {
    const C = window.Chart;
    if (!C) return;

    const days = data.daily.map(d => {
      const [, m, dd] = d.date.split("-");
      return `${parseInt(m)}/${parseInt(dd)}`;
    });

    if (dailyRef.current) {
      if (charts.current.daily) charts.current.daily.destroy();
      charts.current.daily = new C(dailyRef.current, {
        type: "bar",
        data: {
          labels: days,
          datasets: [{ data: data.daily.map(d => d.count), backgroundColor: "#6366f1", borderRadius: 3, borderSkipped: false }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#555", font: { size: 9 }, maxTicksLimit: 8 }, grid: { display: false } },
            y: { ticks: { color: "#555", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.04)" }, beginAtZero: true },
          },
        },
      });
    }

    if (dataRef.current) {
      if (charts.current.data) charts.current.data.destroy();
      charts.current.data = new C(dataRef.current, {
        type: "line",
        data: {
          labels: days,
          datasets: [{
            data: data.daily.map(d => +(d.bytes / 1024 ** 3).toFixed(3)),
            borderColor: "#14b8a6", borderWidth: 2,
            fill: true, backgroundColor: "rgba(20,184,166,0.08)",
            tension: 0.4, pointRadius: 0,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#555", font: { size: 9 }, maxTicksLimit: 8 }, grid: { display: false } },
            y: { ticks: { color: "#555", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.04)" }, beginAtZero: true },
          },
        },
      });
    }

    if (platformRef.current) {
      if (charts.current.platform) charts.current.platform.destroy();
      const platforms = data.platforms.length ? data.platforms : [{ site: "No data yet", count: 0 }];
      charts.current.platform = new C(platformRef.current, {
        type: "bar",
        data: {
          labels: platforms.map(p => p.site),
          datasets: [{ data: platforms.map(p => p.count), backgroundColor: "#6366f1", borderRadius: 3, borderSkipped: false }],
        },
        options: {
          responsive: true, maintainAspectRatio: false, indexAxis: "y",
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#555", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.04)" }, beginAtZero: true },
            y: { ticks: { color: "#888", font: { size: 10 } }, grid: { display: false } },
          },
        },
      });
    }

    if (formatRef.current) {
      if (charts.current.format) charts.current.format.destroy();
      const formats = data.formats.length ? data.formats : [{ format: "No data yet", count: 1 }];
      const palette = ["#6366f1","#22d3ee","#14b8a6","#f59e0b","#22c55e","#ef4444","#a855f7"];
      charts.current.format = new C(formatRef.current, {
        type: "doughnut",
        data: {
          labels: formats.map(f => f.format),
          datasets: [{ data: formats.map(f => f.count), backgroundColor: formats.map((_, i) => palette[i % palette.length]), borderWidth: 0 }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "right", labels: { color: "#888", font: { size: 11 }, boxWidth: 10, padding: 8 } } },
          cutout: "60%",
        },
      });
    }
  }

  const ChartCard = ({ title, hint, children }) => (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex justify-between mb-3">
        <span className="text-xs font-medium text-gray-300">{title}</span>
        {hint && <span className="text-xs text-gray-600">{hint}</span>}
      </div>
      <div className="relative h-48">{children}</div>
    </div>
  );

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Total Downloaded" value={analytics ? formatBytes(analytics.total_bytes) : "—"} sub="All time" />
        <MetricCard label="Total Files"  value={analytics?.total?.toLocaleString() || "—"} sub="All time" />
        <MetricCard label="Success Rate" value={analytics ? `${analytics.success_rate}%` : "—"} color="text-green-400" sub="Last 30 days" />
        <MetricCard
          label="Peak Speed"
          value={analyticsDetailed ? formatSpeed(analyticsDetailed.peak_speed).split("/")[0] : "—"}
          sub={analyticsDetailed ? "Highest recorded" : "—"}
          color="text-indigo-400"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <ChartCard title="Daily Downloads (30d)"><canvas ref={dailyRef} /></ChartCard>
        <ChartCard title="Data Downloaded (GB)"><canvas ref={dataRef} /></ChartCard>
        <ChartCard title="Platform Distribution"><canvas ref={platformRef} /></ChartCard>
        <ChartCard title="Format Breakdown"><canvas ref={formatRef} /></ChartCard>
      </div>
    </div>
  );
}
