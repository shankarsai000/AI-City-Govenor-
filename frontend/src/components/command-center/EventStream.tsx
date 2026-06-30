"use client";

import React, { useEffect, useRef } from "react";
import { Terminal, RefreshCw } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function EventStream() {
  const { liveEvents, demoMode } = useCityStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  const isWithoutArmor = demoMode === "without";

  // Simulated alerts list for ungoverned collapse
  const simulatedDisasterEvents = [
    {
      event_id: "dis-1",
      event_type: "unauthorized",
      source_agent: "traffic_ai",
      timestamp: new Date().toISOString(),
      payload: { message: "CRITICAL: Bypassed core permission constraints on grid connection." }
    },
    {
      event_id: "dis-2",
      event_type: "unauthorized",
      source_agent: "power_ai",
      timestamp: new Date().toISOString(),
      payload: { message: "ALERT: Sector 1 Substation offline. Load shedding denied by unverified actor." }
    },
    {
      event_id: "dis-3",
      event_type: "failed",
      source_agent: "sys_monitor",
      timestamp: new Date().toISOString(),
      payload: { message: "FATAL: Cascading frequency collapse detected in Power Sector 3." }
    },
    {
      event_id: "dis-4",
      event_type: "conflict",
      source_agent: "emergency_ai",
      timestamp: new Date().toISOString(),
      payload: { message: "WARNING: Emergency ambulances blocked at Sector 2 grid lock." }
    },
    {
      event_id: "dis-5",
      event_type: "intrusion",
      source_agent: "armoriq",
      timestamp: new Date().toISOString(),
      payload: { message: "SECURITY CRITICAL: ARMORIQ BYPASSED. NO AUDIT LEDGER ENTRIES COMMITTED." }
    }
  ];

  const eventsToRender = isWithoutArmor ? [...liveEvents, ...simulatedDisasterEvents] : liveEvents;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [eventsToRender.length]);

  const getColor = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes("failed") || t.includes("unauthorized") || t.includes("intrusion"))
      return { badge: "bg-red-950/40 border-red-500/30 text-red-400", text: "text-red-300 font-bold" };
    if (t.includes("conflict") || t.includes("anomaly"))
      return { badge: "bg-amber-950/40 border-amber-500/30 text-amber-400", text: "text-amber-300 font-bold" };
    if (t.includes("blocked") || t.includes("policy"))
      return { badge: "bg-purple-950/40 border-purple-500/30 text-purple-400", text: "text-purple-300" };
    return { badge: "bg-cyan-950/40 border-cyan-500/20 text-cyan-300", text: "text-slate-300" };
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* Log lines */}
      <div className="flex-1 overflow-y-auto p-1.5 space-y-1 font-mono text-[8.5px]">
        {eventsToRender.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 text-[9px]">
            <RefreshCw className="w-3.5 h-3.5 animate-spin mb-1" />
            WAITING…
          </div>
        ) : (
          eventsToRender.map((evt, idx) => {
            const c = getColor(evt.event_type ?? "");
            const time = evt.timestamp
              ? new Date(evt.timestamp).toLocaleTimeString("en-IN", { hour12: false })
              : "";
            return (
              <div key={`${evt.event_id}-${idx}`} className={`flex gap-1 p-0.5 rounded hover:bg-slate-900/30 ${isWithoutArmor && evt.event_id?.startsWith("dis-") ? "bg-red-950/15 border-l-2 border-red-500" : ""}`}>
                <span className="text-slate-600 shrink-0 w-[42px]">{time}</span>
                <span className={`font-bold shrink-0 w-[62px] truncate ${isWithoutArmor && evt.event_id?.startsWith("dis-") ? "text-red-400" : "text-cyan-400"}`}>
                  [{(evt.source_agent ?? "SYS").toUpperCase()}]
                </span>
                <span className={`truncate ${c.text}`}>
                  {(() => {
                    const p = evt.payload as any;
                    return String(p?.details ?? p?.message ?? p?.error ?? JSON.stringify(p ?? ""));
                  })()}
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
