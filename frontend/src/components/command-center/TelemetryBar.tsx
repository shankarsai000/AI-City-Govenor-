"use client";

import React from "react";
import { AreaChart, Shield, Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCityStore } from "@/store/city-store";
import { LiveCharts } from "./LiveCharts";
import { AuditLedger } from "./AuditLedger";
import { SimulationControls } from "./SimulationControls";
import { ThreatCenter } from "./ThreatCenter";

export function TelemetryBar() {
  const {
    activeBottomTab,
    setActiveBottomTab,
    replayBuffer,
    isReplayActive,
    replayIndex,
    setReplayMode,
    scrubTimeline,
    demoMode,
  } = useCityStore();

  const isWithout = demoMode === "without";

  const tabs = [
    { key: "charts" as const, label: "LIVE GRAPHS", icon: <AreaChart className="w-3 h-3" /> },
    { key: "audit" as const, label: "AUDIT LEDGER", icon: <Shield className="w-3 h-3" /> },
    { key: "simulation" as const, label: "SIMULATOR", icon: <Play className="w-3 h-3" /> },
    { key: "threat" as const, label: "THREAT & FORECAST", icon: <ShieldAlert className="w-3 h-3" /> },
  ];

  return (
    <div className={`h-full w-full flex flex-col overflow-hidden transition-colors duration-500 ${isWithout ? "bg-red-950/10" : "bg-slate-950/30"}`}>
      {/* Tab bar */}
      <div className={`h-7 shrink-0 border-b bg-slate-950/60 flex items-center justify-between px-4 font-mono text-[9px] transition-colors duration-500 ${isWithout ? "border-red-500/20" : "border-cyan-500/10"}`}>
        {/* Left Side: Tabs */}
        <div className="flex items-center gap-1 h-full">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveBottomTab(tab.key)}
              className={`px-3 h-full flex items-center gap-1.5 font-bold border-b-2 transition ${
                activeBottomTab === tab.key
                  ? isWithout
                    ? "border-red-400 text-red-300 bg-red-950/20"
                    : "border-cyan-400 text-cyan-300 bg-slate-900/50"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Center: ArmorIQ Shield Status */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border text-[8px] font-bold transition-all duration-500 ${
          isWithout
            ? "border-red-500/30 bg-red-950/30 text-red-400 animate-pulse"
            : "border-emerald-500/20 bg-emerald-950/20 text-emerald-400"
        }`}>
          {isWithout ? (
            <><ShieldAlert className="w-3 h-3" /> ARMORIQ: OFFLINE</>
          ) : (
            <><ShieldCheck className="w-3 h-3" /> ARMORIQ: ACTIVE</>
          )}
        </div>

        {/* Right Side: Timeline Scrubber */}
        <div className="flex items-center gap-3 text-[9px] h-full py-0.5">
          <button
            onClick={() => setReplayMode(!isReplayActive)}
            className={`px-2 py-0.5 rounded border font-bold text-[8.5px] transition ${
              isReplayActive
                ? "bg-amber-950/40 border-amber-500/30 text-amber-400 animate-pulse"
                : "bg-emerald-950/40 border-emerald-500/30 text-emerald-400"
            }`}
          >
            {isReplayActive ? "Timeline: REPLAY" : "Timeline: LIVE"}
          </button>

          {replayBuffer.length > 0 ? (
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={replayBuffer.length - 1}
                value={isReplayActive ? replayIndex : replayBuffer.length - 1}
                disabled={!isReplayActive}
                onChange={(e) => scrubTimeline(Number(e.target.value))}
                className="w-40 accent-cyan-400 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
              />
              <span className="text-slate-500 font-mono text-[8px] min-w-[52px]">
                {isReplayActive
                  ? `T-${(replayBuffer.length - 1 - replayIndex) * 5}s AGO`
                  : "REALTIME"}
              </span>
            </div>
          ) : (
            <span className="text-slate-600 text-[8px]">BUFFERING TRACK…</span>
          )}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeBottomTab === "charts" && <LiveCharts />}
        {activeBottomTab === "audit" && <AuditLedger />}
        {activeBottomTab === "simulation" && <SimulationControls />}
        {activeBottomTab === "threat" && <ThreatCenter />}
      </div>
    </div>
  );
}
