"use client";

import React, { useEffect, useState } from "react";
import { Brain, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function AgentCards() {
  const { agents, demoMode } = useCityStore();
  const [metrics, setMetrics] = useState<
    Record<string, { conf: number; cpu: number; mem: number; thought: string }>
  >({});

  const isWithout = demoMode === "without";

  useEffect(() => {
    const safeThoughts = [
      "EVALUATING TOPOLOGY",
      "STABILIZING PRESSURE",
      "ANALYZING LOAD SHIFT",
      "POLICY AUDIT",
      "POLLING ANOMALIES",
      "MONITORING LOOPS",
    ];
    const dangerThoughts = [
      "GOVERNANCE BYPASSED",
      "UNAUTHORIZED ACCESS",
      "CASCADE FAILURE",
      "GRID OVERLOAD",
      "INTEGRITY BREACH",
      "NO AUDIT TRAIL",
    ];
    const thoughts = isWithout ? dangerThoughts : safeThoughts;

    const update = () => {
      const m: typeof metrics = {};
      agents.forEach((a) => {
        m[a.agent_id] = {
          conf: isWithout ? 15 + Math.round(Math.random() * 30) : 85 + Math.round(Math.random() * 14),
          cpu: isWithout ? 70 + Math.round(Math.random() * 28) : 12 + Math.round(Math.random() * 45),
          mem: isWithout ? 65 + Math.round(Math.random() * 30) : 30 + Math.round(Math.random() * 25),
          thought: thoughts[Math.floor(Math.random() * thoughts.length)] ?? "IDLE",
        };
      });
      setMetrics(m);
    };
    update();
    const id = setInterval(update, 4000);
    return () => clearInterval(id);
  }, [agents, isWithout]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Title */}
      <div className="px-3 py-1.5 border-b border-cyan-500/10 bg-slate-950/50 shrink-0 flex items-center justify-between">
        <span className="text-[9px] tracking-[0.15em] font-mono text-cyan-400 font-bold flex items-center gap-1">
          <Brain className="w-3 h-3" />
          AGENT FLEET
        </span>
        <span className={`text-[8px] font-mono font-bold flex items-center gap-1 ${isWithout ? "text-red-400" : "text-slate-600"}`}>
          {isWithout ? (
            <><ShieldAlert className="w-2.5 h-2.5 text-red-400" /> UNGOVERNED</>
          ) : (
            <><ShieldCheck className="w-2.5 h-2.5 text-emerald-400" /> {agents.length} GOVERNED</>
          )}
        </span>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-1.5 grid grid-cols-2 gap-1.5 auto-rows-min">
        {agents.map((agent) => {
          const m = metrics[agent.agent_id] ?? { conf: 95, cpu: 25, mem: 40, thought: "PROCESSING" };
          const confColor = isWithout
            ? m.conf < 30 ? "text-red-400" : "text-amber-400"
            : "text-emerald-400";
          const cardBorder = isWithout
            ? "border-red-500/15 bg-red-950/10"
            : "border-cyan-500/5 bg-slate-950/30";
          const dotColor = isWithout
            ? "bg-red-400 animate-pulse"
            : "bg-cyan-400 animate-pulse";
          const thoughtBg = isWithout
            ? "bg-red-950/30 border-red-500/10 text-red-400/80"
            : "bg-slate-950/50 border-cyan-500/5 text-cyan-400/80";
          const barGradient = isWithout
            ? "from-red-500 to-amber-500"
            : "from-cyan-500 to-purple-500";

          return (
            <div
              key={agent.agent_id}
              className={`p-1.5 rounded border flex flex-col gap-1 transition-all duration-500 ${cardBorder}`}
            >
              {/* Name + domain */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 font-mono">
                  <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
                  <span className={`text-[9px] font-bold truncate max-w-[60px] ${isWithout ? "text-red-300" : "text-cyan-300"}`}>
                    {agent.name.replace("_agent", "").toUpperCase()}
                  </span>
                </div>
                <span className="text-[7px] font-mono text-slate-600 font-bold bg-slate-900 px-1 rounded">
                  {agent.domain}
                </span>
              </div>

              {/* Thinking */}
              <div className={`px-1 py-0.5 border rounded font-mono text-[7px] truncate flex items-center gap-1 transition-colors duration-500 ${thoughtBg}`}>
                <span className={`w-1 h-1 rounded-full shrink-0 ${isWithout ? "bg-red-400/50 animate-ping" : "bg-cyan-400/50 animate-ping"}`} />
                {m.thought}
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-3 gap-0.5 text-[7px] font-mono text-slate-500">
                <div>CPU <strong className={isWithout && m.cpu > 80 ? "text-red-400 block" : "text-slate-300 block"}>{m.cpu}%</strong></div>
                <div>MEM <strong className={isWithout && m.mem > 80 ? "text-red-400 block" : "text-slate-300 block"}>{m.mem}%</strong></div>
                <div>CONF <strong className={`${confColor} block`}>{m.conf}%</strong></div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-950/60 h-0.5 rounded-full overflow-hidden">
                <div
                  className={`h-full bg-gradient-to-r ${barGradient} rounded-full`}
                  style={{ width: `${m.conf}%`, transition: "width 1s ease" }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
