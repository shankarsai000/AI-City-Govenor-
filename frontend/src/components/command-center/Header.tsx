"use client";

import React, { useEffect, useState } from "react";
import { Shield, Activity, Cpu, Radio, AlertTriangle } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function Header() {
  const { session, wsConnected, telemetry, summary } = useCityStore();
  const [timeStr, setTimeStr] = useState("");

  useEffect(() => {
    const updateTime = () => {
      const d = new Date();
      setTimeStr(
        d.toLocaleTimeString("en-IN", {
          hour12: false,
          timeZone: "Asia/Kolkata",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }) + " IST"
      );
    };
    updateTime();
    const id = setInterval(updateTime, 1000);
    return () => clearInterval(id);
  }, []);

  const alertCount = summary?.alerts.length ?? 0;
  const threat =
    alertCount > 2 ? "CRITICAL" : alertCount > 0 ? "ELEVATED" : "NOMINAL";
  const threatCls =
    threat === "CRITICAL"
      ? "text-red-400 border-red-500/30 bg-red-950/20"
      : threat === "ELEVATED"
      ? "text-yellow-400 border-yellow-500/30 bg-yellow-950/20"
      : "text-emerald-400 border-emerald-500/30 bg-emerald-950/20";

  return (
    <header className="h-full bg-slate-950/80 backdrop-blur border-b border-cyan-500/10 flex items-center justify-between px-5 font-mono text-[11px]">
      {/* Left — Branding */}
      <div className="flex items-center gap-3 shrink-0">
        <Shield className="w-4 h-4 text-cyan-400" />
        <span className="font-bold tracking-[0.15em] text-cyan-300 text-xs">
          AI CITY GOVERNOR
        </span>
        <span className="hidden xl:inline text-[9px] tracking-[0.2em] text-slate-500">
          SMART CITY COMMAND CENTER
        </span>
      </div>

      {/* Center — Telemetry Strip */}
      <div className="flex items-center gap-5 text-slate-400">
        <div>
          <span className="text-slate-500">CLOCK </span>
          <span className="text-cyan-400 font-bold tracking-wider">{timeStr}</span>
        </div>
        <div className="flex items-center gap-1">
          <Activity className="w-3 h-3 text-cyan-500" />
          <span className="text-slate-500">LAT </span>
          <span className="text-cyan-400 font-bold">{telemetry.latency}ms</span>
        </div>
        <div className="flex items-center gap-1">
          <Cpu className="w-3 h-3 text-cyan-500" />
          <span className="text-slate-500">FPS </span>
          <span className="text-cyan-400 font-bold">{telemetry.fps}</span>
        </div>
        <div className="flex items-center gap-1">
          <Radio className="w-3 h-3 text-cyan-500" />
          <span className="text-slate-500">EVT </span>
          <span className="text-cyan-400 font-bold">{telemetry.eventsPerSec}/s</span>
        </div>

        {/* Connection dot */}
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              wsConnected
                ? "bg-emerald-500 shadow-[0_0_6px_#10b981]"
                : "bg-red-500 shadow-[0_0_6px_#ef4444] animate-pulse"
            }`}
          />
          <span className={wsConnected ? "text-emerald-400" : "text-red-400"}>
            {wsConnected ? "LIVE" : "OFFLINE"}
          </span>
        </div>

        {/* Threat badge */}
        <div
          className={`px-2 py-0.5 border rounded text-[10px] font-bold flex items-center gap-1 ${threatCls}`}
        >
          <AlertTriangle className="w-3 h-3" />
          {threat}
        </div>
      </div>

      {/* Right — Operator */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-slate-500">OPR:</span>
        <span className="text-cyan-300 font-bold">
          {session?.username?.toUpperCase() ?? "GUEST"}
        </span>
        <span className="bg-cyan-950/40 border border-cyan-500/20 text-cyan-300 px-1.5 py-0.5 rounded text-[9px] font-bold">
          {session?.role?.toUpperCase() ?? "—"}
        </span>
      </div>
    </header>
  );
}
