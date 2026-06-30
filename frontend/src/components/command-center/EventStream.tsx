"use client";

import React, { useEffect, useRef } from "react";
import { Terminal, RefreshCw } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function EventStream() {
  const { liveEvents } = useCityStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveEvents.length]);

  const getColor = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes("failed") || t.includes("unauthorized") || t.includes("intrusion"))
      return { badge: "bg-red-950/40 border-red-500/30 text-red-400", text: "text-red-300" };
    if (t.includes("conflict") || t.includes("anomaly"))
      return { badge: "bg-amber-950/40 border-amber-500/30 text-amber-400", text: "text-amber-300" };
    if (t.includes("blocked") || t.includes("policy"))
      return { badge: "bg-purple-950/40 border-purple-500/30 text-purple-400", text: "text-purple-300" };
    return { badge: "bg-cyan-950/40 border-cyan-500/20 text-cyan-300", text: "text-slate-300" };
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* Log lines */}
      <div className="flex-1 overflow-y-auto p-1.5 space-y-1 font-mono text-[8.5px]">
        {liveEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 text-[9px]">
            <RefreshCw className="w-3.5 h-3.5 animate-spin mb-1" />
            WAITING…
          </div>
        ) : (
          liveEvents.map((evt, idx) => {
            const c = getColor(evt.event_type ?? "");
            const time = evt.timestamp
              ? new Date(evt.timestamp).toLocaleTimeString("en-IN", { hour12: false })
              : "";
            return (
              <div key={`${evt.event_id}-${idx}`} className="flex gap-1 p-0.5 rounded hover:bg-slate-900/30">
                <span className="text-slate-600 shrink-0 w-[42px]">{time}</span>
                <span className="text-cyan-400 font-bold shrink-0 w-[62px] truncate">
                  [{(evt.source_agent ?? "SYS").toUpperCase()}]
                </span>
                <span className={`truncate ${c.text}`}>
                  {String(
                    evt.payload?.details ??
                    evt.payload?.message ??
                    evt.payload?.error ??
                    JSON.stringify(evt.payload)
                  )}
                </span>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
