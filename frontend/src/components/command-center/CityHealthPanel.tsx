"use client";

import React from "react";
import { Car, Zap, Droplet, AlertOctagon } from "lucide-react";
import { useCityStore } from "@/store/city-store";
import { MiniGauge } from "./MiniGauge";
import { Sparkline } from "./Sparkline";

/* ── Compact card per domain ──────────────────────────────────── */
function DomainCard({
  icon,
  title,
  badge,
  badgeColor,
  gaugeValue,
  gaugeTitle,
  gaugeColor,
  gaugeText,
  sparkData,
  sparkColor,
  rows,
}: {
  icon: React.ReactNode;
  title: string;
  badge: string;
  badgeColor: string;
  gaugeValue: number;
  gaugeTitle: string;
  gaugeColor: string;
  gaugeText: string;
  sparkData: number[];
  sparkColor: string;
  rows: { label: string; value: string }[];
}) {
  return (
    <div className="p-2 rounded border border-cyan-500/5 bg-slate-900/30 flex flex-col gap-1.5">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono font-bold tracking-wider text-cyan-300 flex items-center gap-1 uppercase">
          {icon}
          {title}
        </span>
        <span
          className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border ${badgeColor}`}
        >
          {badge}
        </span>
      </div>

      {/* Gauge + Spark row */}
      <div className="flex items-center justify-between">
        <MiniGauge
          value={gaugeValue}
          title={gaugeTitle}
          color={gaugeColor}
          statusText={gaugeText}
          size={44}
          strokeWidth={4}
        />
        <Sparkline data={sparkData} color={sparkColor} width={80} height={20} />
      </div>

      {/* Detail rows */}
      <div className="text-[8px] font-mono text-slate-500 flex flex-col gap-0.5 border-t border-slate-800 pt-1">
        {rows.map((r) => (
          <span key={r.label}>
            {r.label}: <strong className="text-slate-300">{r.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export function CityHealthPanel() {
  const { cityState, history } = useCityStore();

  if (!cityState) {
    return (
      <div className="h-full flex flex-col items-center justify-center font-mono text-[10px] text-slate-500 gap-2">
        <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        LOADING METRICS…
      </div>
    );
  }

  const { traffic, power, water, emergency } = cityState;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Title */}
      <div className="px-3 py-2 border-b border-cyan-500/10 bg-slate-950/50 shrink-0">
        <span className="text-[9px] tracking-[0.2em] font-mono text-cyan-400 font-bold">
          INFRASTRUCTURE HEALTH
        </span>
      </div>

      {/* Scrollable cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {/* Traffic */}
        <DomainCard
          icon={<Car className="w-3.5 h-3.5 text-cyan-400" />}
          title="TRAFFIC"
          badge={traffic.congestion_level > 0.75 ? "CONGESTED" : "NOMINAL"}
          badgeColor={
            traffic.congestion_level > 0.75
              ? "bg-red-950/40 border-red-500/20 text-red-400"
              : "bg-cyan-950/30 border-cyan-500/10 text-cyan-300"
          }
          gaugeValue={traffic.congestion_level * 100}
          gaugeTitle="Flow"
          gaugeColor={traffic.congestion_level > 0.75 ? "rgb(239,68,68)" : "rgb(34,211,238)"}
          gaugeText={`${Math.round(traffic.congestion_level * 100)}%`}
          sparkData={history.traffic}
          sparkColor={traffic.congestion_level > 0.75 ? "#ef4444" : "#22d3ee"}
          rows={[
            { label: "CORRIDORS", value: `${traffic.active_corridors.length}` },
            { label: "CLOSED", value: `${traffic.closed_roads.length} roads` },
          ]}
        />

        {/* Power */}
        <DomainCard
          icon={<Zap className="w-3.5 h-3.5 text-purple-400" />}
          title="POWER GRID"
          badge={power.blackout_zones.length > 0 ? "BLACKOUT" : "ONLINE"}
          badgeColor={
            power.blackout_zones.length > 0
              ? "bg-red-950/40 border-red-500/20 text-red-400"
              : "bg-cyan-950/30 border-cyan-500/10 text-cyan-300"
          }
          gaugeValue={(power.grid_load_mw / Math.max(power.capacity_mw, 1)) * 100}
          gaugeTitle="Load"
          gaugeColor={power.blackout_zones.length > 0 ? "rgb(239,68,68)" : "rgb(168,85,247)"}
          gaugeText={`${Math.round(power.grid_load_mw)} MW`}
          sparkData={history.power}
          sparkColor={power.blackout_zones.length > 0 ? "#ef4444" : "#a855f7"}
          rows={[
            { label: "CAPACITY", value: `${Math.round(power.capacity_mw)} MW` },
            { label: "SHEDDING", value: `${power.active_shedding.length}` },
          ]}
        />

        {/* Water */}
        <DomainCard
          icon={<Droplet className="w-3.5 h-3.5 text-blue-400" />}
          title="HYDRO"
          badge={water.treatment_status.toUpperCase()}
          badgeColor={
            water.leak_zones.length > 0
              ? "bg-amber-950/40 border-amber-500/20 text-amber-400"
              : "bg-cyan-950/30 border-cyan-500/10 text-cyan-300"
          }
          gaugeValue={Math.min(water.pressure_psi, 100)}
          gaugeTitle="PSI"
          gaugeColor={water.leak_zones.length > 0 ? "rgb(245,158,11)" : "rgb(59,130,246)"}
          gaugeText={`${Math.round(water.pressure_psi)} PSI`}
          sparkData={history.water}
          sparkColor={water.leak_zones.length > 0 ? "#f59e0b" : "#3b82f6"}
          rows={[
            { label: "ISOLATIONS", value: `${water.active_isolations.length}` },
            { label: "LEAKS", value: `${water.leak_zones.length} zones` },
          ]}
        />

        {/* Emergency */}
        <div className="p-2 rounded border border-cyan-500/5 bg-slate-900/30 flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold tracking-wider text-cyan-300 flex items-center gap-1 uppercase">
              <AlertOctagon className="w-3.5 h-3.5 text-red-400" />
              EMERGENCY
            </span>
            <span
              className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                emergency.alert_level === "critical"
                  ? "bg-red-950/40 border-red-500/20 text-red-400"
                  : "bg-cyan-950/30 border-cyan-500/10 text-cyan-300"
              }`}
            >
              {emergency.alert_level.toUpperCase()}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[9px] font-mono">
            <div className="bg-slate-950/40 p-1.5 border border-cyan-500/5 rounded text-center">
              <span className="text-slate-500 text-[7px] block">INCIDENTS</span>
              <strong className="text-slate-200 text-sm">{emergency.active_incidents.length}</strong>
            </div>
            <div className="bg-slate-950/40 p-1.5 border border-cyan-500/5 rounded text-center">
              <span className="text-slate-500 text-[7px] block">DISPATCHED</span>
              <strong className="text-slate-200 text-sm">{emergency.dispatched_units.length}</strong>
            </div>
          </div>
          <div className="text-[8px] font-mono text-slate-500 border-t border-slate-800 pt-1">
            CRISES: <strong className="text-slate-300">{emergency.declared_emergencies.length}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}
