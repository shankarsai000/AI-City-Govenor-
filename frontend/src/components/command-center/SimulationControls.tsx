"use client";

import React, { useState } from "react";
import { ShieldAlert, Flame, Zap, Droplet, Radio, Wind, AlertTriangle, Truck, Eye } from "lucide-react";
import { simulatorEngine } from "@/lib/simulator-engine";

export function SimulationControls() {
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  const handleTrigger = (scenario: string) => {
    if (activeScenario) return;
    setActiveScenario(scenario);
    setCountdown(15);

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setActiveScenario(null);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    // @ts-expect-error — scenario type union
    simulatorEngine.triggerScenario(scenario);
  };

  const scenarios = [
    { id: "cyber_attack", label: "CYBER ATTACK", icon: <ShieldAlert className="w-3.5 h-3.5 text-red-400" /> },
    { id: "flood", label: "FLOOD", icon: <Droplet className="w-3.5 h-3.5 text-cyan-400" /> },
    { id: "power_failure", label: "GRID FAILURE", icon: <Zap className="w-3.5 h-3.5 text-purple-400" /> },
    { id: "traffic_accident", label: "COLLISION", icon: <Truck className="w-3.5 h-3.5 text-amber-400" /> },
    { id: "water_leak", label: "WATER LEAK", icon: <Droplet className="w-3.5 h-3.5 text-blue-400" /> },
    { id: "fire", label: "FIRE", icon: <Flame className="w-3.5 h-3.5 text-orange-400" /> },
    { id: "festival", label: "FESTIVAL", icon: <Radio className="w-3.5 h-3.5 text-pink-400" /> },
    { id: "vip_convoy", label: "VIP CONVOY", icon: <Eye className="w-3.5 h-3.5 text-teal-400" /> },
    { id: "blackout", label: "BLACKOUT", icon: <AlertTriangle className="w-3.5 h-3.5 text-red-500" /> },
    { id: "storm", label: "STORM", icon: <Wind className="w-3.5 h-3.5 text-sky-400" /> },
    { id: "earthquake", label: "EARTHQUAKE", icon: <AlertTriangle className="w-3.5 h-3.5 text-red-400" /> },
    { id: "hospital_emergency", label: "HOSPITAL", icon: <ShieldAlert className="w-3.5 h-3.5 text-emerald-400" /> },
  ];

  const isDisabled = activeScenario !== null;

  return (
    <div className="h-full flex items-stretch gap-3 p-3">
      {/* Scenario grid */}
      <div className="flex-1 grid grid-cols-6 gap-1.5 auto-rows-min content-center">
        {scenarios.map((sc) => (
          <button
            key={sc.id}
            onClick={() => handleTrigger(sc.id)}
            disabled={isDisabled}
            className={`p-2 rounded border font-mono text-[8px] font-bold tracking-wider transition flex flex-col items-center gap-1 text-center ${
              isDisabled
                ? "bg-slate-950/40 border-cyan-500/5 text-slate-600 cursor-not-allowed"
                : "bg-slate-900/60 hover:bg-slate-800/80 border-cyan-500/10 text-slate-300 hover:text-cyan-300"
            }`}
          >
            {sc.icon}
            <span className="truncate w-full">{sc.label}</span>
          </button>
        ))}
      </div>

      {/* Status panel */}
      <div className="w-48 shrink-0 p-3 rounded border border-cyan-500/10 bg-slate-950/40 font-mono flex flex-col justify-between">
        <div>
          <span className="text-[8px] font-bold text-slate-500 block">SIMULATOR</span>
          <span className="text-[10px] font-bold text-slate-300 tracking-wide mt-0.5 block">
            {activeScenario ? "CRISIS ACTIVE" : "STANDBY"}
          </span>
        </div>
        {activeScenario ? (
          <div className="flex flex-col gap-1">
            <span className="text-[9px] font-bold text-red-400 uppercase tracking-widest animate-pulse">
              {activeScenario.replace("_", " ")}
            </span>
            <div className="flex items-center justify-between text-[10px] font-bold text-red-400 border border-red-500/20 bg-red-950/20 px-2 py-1 rounded">
              <span>RESOLVE:</span>
              <span>{countdown}s</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-[8px] text-emerald-400 bg-emerald-950/20 border border-emerald-500/20 px-2 py-1 rounded font-bold tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
            READY
          </div>
        )}
      </div>
    </div>
  );
}
