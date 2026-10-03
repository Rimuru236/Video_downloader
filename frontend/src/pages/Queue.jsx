// src/pages/Queue.jsx
import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { api } from "../services/api";
import { Button, StatusPill, formatBytes } from "../components/ui";

const PRIO_STYLE = {
  1: "bg-red-500/15 text-red-400",
  2: "bg-red-500/15 text-red-400",
  3: "bg-amber-500/15 text-amber-400",
  4: "bg-amber-500/15 text-amber-400",
  5: "bg-gray-700/50 text-gray-400",
};
const PRIO_LABEL = { 1:"Critical", 2:"High", 3:"Medium", 4:"Low", 5:"Normal" };

export default function Queue() {
  const { queue, fetchQueue, toast } = useStore();
  const [dragIndex, setDragIndex] = useState(null);
  const [reordering, setReordering] = useState(false);

  async function act(fn, msg) {
    try { await fn(); toast(msg, "success"); await fetchQueue(); }
    catch (e) { toast(e.message, "error"); }
  }

  // FE-1: reorderQueue() already existed on both the API client and the
  // backend — nothing in the UI ever called it. The drag handle (⠿) shown
  // next to every item was purely decorative. Native HTML5 drag-and-drop:
  // on drop, splice the dragged item into its new spot and persist
  // sequential positions for every item (not just the moved one), since
  // QueueManager.reorder() only sets whatever position value it's given
  // for a single item — renumbering everyone keeps the whole list
  // consistent with what's now on screen instead of just the one row.
  async function handleDrop(toIndex) {
    const fromIndex = dragIndex;
    setDragIndex(null);
    if (fromIndex === null || fromIndex === toIndex) return;

    const items = [...queue];
    const [moved] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, moved);

    setReordering(true);
    try {
      await Promise.all(items.map((item, idx) =>
        api.reorderQueue({ download_id: item.download_id, new_position: idx })
      ));
      await fetchQueue();
    } catch (e) {
      toast(e.message, "error");
      await fetchQueue();
    } finally {
      setReordering(false);
    }
  }

  const totalSize = queue.reduce((s, q) => s + (q.filesize || 0), 0);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button variant="primary" onClick={() => act(api.startQueue, "Queue started")}>▶ Start Queue</Button>
        <Button onClick={() => act(api.pauseQueue, "Queue paused")}>⏸ Pause All</Button>
        <Button variant="danger" onClick={() => act(api.clearQueue, "Queue cleared")}>✕ Clear Queue</Button>
        <div className="ml-auto text-xs text-gray-600">
          {queue.length} items{totalSize > 0 ? ` · ${formatBytes(totalSize)} total` : ""}
        </div>
      </div>

      {/* Queue list */}
      <div className="space-y-2">
        {queue.map((item, i) => (
          <div
            key={item.queue_id}
            draggable={!reordering}
            onDragStart={() => setDragIndex(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => handleDrop(i)}
            onDragEnd={() => setDragIndex(null)}
            className={`bg-gray-900 border rounded-xl px-4 py-3 flex items-center gap-3 transition-colors ${
              dragIndex === i ? "border-indigo-500 opacity-50" : "border-gray-800 hover:border-gray-700"
            }`}
          >
            <span className="text-gray-700 cursor-grab select-none text-base">⠿</span>
            <span className="text-xs font-mono text-gray-700 w-5 text-right">{i + 1}</span>
            <div className="w-11 h-7 rounded bg-gray-800 flex items-center justify-center text-gray-700 flex-shrink-0">▶</div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-gray-200 truncate">{item.title || item.url}</div>
              <div className="text-xs text-gray-600 mt-0.5">
                {item.source_site || "—"} · {item.resolution || "—"} · {formatBytes(item.filesize)}
              </div>
            </div>
            <StatusPill status={item.status} />
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIO_STYLE[item.priority] || PRIO_STYLE[5]}`}>
              {PRIO_LABEL[item.priority] || "Normal"}
            </span>
            <button
              onClick={() => act(() => api.removeFromQueue(item.download_id), "Removed from queue")}
              aria-label="Remove from queue"
              className="w-6 h-6 rounded flex items-center justify-center text-gray-700 hover:text-red-400 hover:bg-red-500/10 transition-colors text-xs"
            >✕</button>
          </div>
        ))}
        {queue.length === 0 && (
          <div className="text-center py-16 text-gray-700">
            <div className="text-3xl mb-2">≡</div>
            <div className="text-sm">Queue is empty</div>
          </div>
        )}
      </div>
    </div>
  );
}
