"use client";

/* ═══════════════════════════════════════════════════════════════════
   AI CITY GOVERNOR — SMART CITY COMMAND CENTER
   Root layout: Header → [Left | Center | Right] → Bottom
   Fullscreen, zero-scroll, professional aerospace grid.
   ═══════════════════════════════════════════════════════════════════ */

import React, { useEffect, useState } from "react";
import { Activity, ShieldAlert } from "lucide-react";
import { useCityStore } from "@/store/city-store";
import { simulatorEngine } from "@/lib/simulator-engine";

import { Header } from "./Header";
import { CityHealthPanel } from "./CityHealthPanel";
import { DigitalTwinCanvas } from "./DigitalTwinCanvas";
import { EventStream } from "./EventStream";
import { AgentConversations } from "./AgentConversations";
import { AgentCards } from "./AgentCards";
import { GovernancePipeline } from "./GovernancePipeline";
import { TelemetryBar } from "./TelemetryBar";

export function CommandCenter() {
  const { initialize, cleanup, loading, error, isAuthenticated } = useCityStore();
  const [rightTab, setRightTab] = useState<"logs" | "chat">("logs");

  useEffect(() => {
    void initialize();
    simulatorEngine.start();
    return () => {
      cleanup();
      simulatorEngine.stop();
    };
  }, [initialize, cleanup]);

  /* ── Loading screen ───────────────────────────────────────────── */
  if (loading && !isAuthenticated) {
    return (
      <main className="h-screen w-screen bg-slate-950 flex items-center justify-center font-mono select-none">
        <div className="flex flex-col items-center gap-4 text-center max-w-sm p-8 rounded-lg border border-cyan-500/10 bg-slate-900/30 backdrop-blur">
          <Activity className="w-8 h-8 text-cyan-400 animate-spin" />
          <span className="text-xs tracking-[0.25em] text-cyan-400 font-bold uppercase">
            System Initialization
          </span>
          <h1 className="text-sm font-bold text-slate-100 uppercase tracking-widest">
            Establishing Operator Session
          </h1>
          <p className="text-[10px] text-slate-500 leading-relaxed uppercase">
            Securing auth channels, compiling ledger chains, mounting digital twin…
          </p>
        </div>
      </main>
    );
  }

  /* ── Error screen ─────────────────────────────────────────────── */
  if (error && !isAuthenticated) {
    return (
      <main className="h-screen w-screen bg-slate-950 flex items-center justify-center font-mono select-none">
        <div className="flex flex-col items-center gap-4 text-center max-w-md p-8 rounded-lg border border-red-500/20 bg-slate-900/30 backdrop-blur">
          <ShieldAlert className="w-8 h-8 text-red-500 animate-bounce" />
          <span className="text-xs tracking-[0.25em] text-red-400 font-bold uppercase">
            Critical Fault
          </span>
          <h1 className="text-sm font-bold text-slate-100 uppercase tracking-widest">
            Connection Terminal Failure
          </h1>
          <p className="text-[10px] text-red-400/80 border border-red-500/20 bg-red-950/20 p-3 rounded w-full break-words">
            {error}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="w-full bg-cyan-950/60 hover:bg-cyan-900/80 border border-cyan-500/30 text-cyan-300 text-xs font-bold py-2.5 rounded tracking-widest uppercase transition"
          >
            Re-Authenticate Link
          </button>
        </div>
      </main>
    );
  }

  /* ── Main Dashboard Grid ──────────────────────────────────────── */
  return (
    <main
      className="h-screen w-screen bg-slate-950 text-slate-200 overflow-hidden select-none"
      style={{
        display: "grid",
        gridTemplateRows: "48px 1fr 200px",
        gridTemplateColumns: "260px 1fr 320px",
        gridTemplateAreas: `
          "header  header  header"
          "left    center  right"
          "bottom  bottom  bottom"
        `,
      }}
    >
      {/* Row 1 — Header */}
      <div style={{ gridArea: "header" }}>
        <Header />
      </div>

      {/* Row 2 Col 1 — Left: City Health */}
      <div
        style={{ gridArea: "left" }}
        className="border-r border-cyan-500/10 overflow-hidden"
      >
        <CityHealthPanel />
      </div>

      {/* Row 2 Col 2 — Center: Digital Twin */}
      <div
        style={{ gridArea: "center" }}
        className="overflow-hidden relative"
      >
        <DigitalTwinCanvas />
      </div>

      {/* Row 2 Col 3 — Right: Events + Agents + Pipeline */}
      <div
        style={{ gridArea: "right" }}
        className="border-l border-cyan-500/10 overflow-hidden flex flex-col"
      >
        {/* Top 40% — Event Stream / Conversations */}
        <div className="flex-[4] min-h-0 overflow-hidden border-b border-cyan-500/10 flex flex-col">
          <div className="h-7 shrink-0 border-b border-cyan-500/10 bg-slate-950/60 flex items-center px-3 gap-2 font-mono text-[9px]">
            <button
              onClick={() => setRightTab("logs")}
              className={`h-full border-b-2 px-2 font-bold transition ${
                rightTab === "logs"
                  ? "border-cyan-400 text-cyan-300 bg-slate-900/30"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              EVENT MONITOR
            </button>
            <button
              onClick={() => setRightTab("chat")}
              className={`h-full border-b-2 px-2 font-bold transition ${
                rightTab === "chat"
                  ? "border-cyan-400 text-cyan-300 bg-slate-900/30"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              AGENT CHAT
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            {rightTab === "logs" ? <EventStream /> : <AgentConversations />}
          </div>
        </div>
        {/* Middle 35% — Agent Cards */}
        <div className="flex-[3.5] min-h-0 overflow-hidden border-b border-cyan-500/10">
          <AgentCards />
        </div>
        {/* Bottom 25% — Governance Pipeline */}
        <div className="flex-[2.5] min-h-0 overflow-hidden">
          <GovernancePipeline />
        </div>
      </div>

      {/* Row 3 — Bottom Telemetry Bar (full width) */}
      <div style={{ gridArea: "bottom" }} className="border-t border-cyan-500/10 overflow-hidden">
        <TelemetryBar />
      </div>
    </main>
  );
}

export default CommandCenter;
