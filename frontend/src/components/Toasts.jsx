// src/components/Toasts.jsx
import React from "react";
import { useStore } from "../store/useStore";

export default function Toasts() {
  const { toasts } = useStore();
  if (!toasts.length) return null;
  return (
    <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm shadow-xl border transition-all
            ${t.type === "success" ? "bg-green-950 border-green-800 text-green-300" :
              t.type === "error"   ? "bg-red-950   border-red-800   text-red-300"   :
                                     "bg-gray-900   border-gray-700  text-gray-200"}`}
        >
          <span>{t.type === "success" ? "✓" : t.type === "error" ? "✕" : "ℹ"}</span>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
