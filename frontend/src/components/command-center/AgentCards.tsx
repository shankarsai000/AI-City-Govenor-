"use client";

import React, { useEffect, useState } from "react";
import { Brain } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function AgentCards() {
  const { agents } = useCityStore();
  const [metrics, setMetrics] = useState<
    Record<string, { conf: number; cpu: number; mem: number; thought: string }>
  >({});

  useEffect(() => {
    const thoughts = [
      "EVALUATING TOPOLOGY",
      "STABILIZING PRESSURE",
      "ANALYZING LOAD SHIFT",
      "POLICY AUDIT",
      "POLLING ANOMALIES",
      "MONITORING LOOPS",
    ];
    const update = () => {
      const m: typeof metrics = {};
      agents.forEach((a) => {
        m[a.agent_id] = {
          conf: 85 + Math.round(Math.random() * 14),
          cpu: 12 + Math.round(Math.random() * 45),
          mem: 30 + Math.round(Math.random() * 25),
          thought: thoughts[Math.floor(Math.random() * thoughts.length)] ?? "IDLE",
        };
      });
      setMetrics(m);
    };
    update();
    const id = setInterval(update, 4000);
    return () => clearInterval(id);
  }, [agents]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Title */}
      <div className="px-3 py-1.5 border-b border-cyan-500/10 bg-slate-950/50 shrink-0 flex items-center justify-between">
        <span className="text-[9px] tracking-[0.15em] font-mono text-cyan-400 font-bold flex items-center gap-1">
          <Brain className="w-3 h-3" />
          AGENT FLEET
        </span>
        <span className="text-[8px] font-mono text-slate-600">
          {agents.length} ONLINE
        </span>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-1.5 grid grid-cols-2 gap-1.5 auto-rows-min">
        {agents.map((agent) => {
          const m = metrics[agent.agent_id] ?? { conf: 95, cpu: 25, mem: 40, thought: "PROCESSING" };
          return (
            <div
              key={agent.agent_id}
              className="p-1.5 rounded border border-cyan-500/5 bg-slate-950/30 flex flex-col gap-1"
            >
              {/* Name + domain */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  <span className="text-[9px] font-bold text-cyan-300 truncate max-w-[60px]">
                    {agent.name.replace("_agent", "").toUpperCase()}
                  </span>
                </div>
                <span className="text-[7px] font-mono text-slate-600 font-bold bg-slate-900 px-1 rounded">
                  {agent.domain}
                </span>
              </div>

              {/* Thinking */}
              <div className="bg-slate-950/50 px-1 py-0.5 border border-cyan-500/5 rounded font-mono text-[7px] text-cyan-400/80 truncate flex items-center gap-1">
                <span className="w-1 h-1 rounded-full bg-cyan-400/50 animate-ping shrink-0" />
                {m.thought}
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-3 gap-0.5 text-[7px] font-mono text-slate-500">
                <div>CPU <strong className="text-slate-300 block">{m.cpu}%</strong></div>
                <div>MEM <strong className="text-slate-300 block">{m.mem}%</strong></div>
                <div>CONF <strong className="text-emerald-400 block">{m.conf}%</strong></div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-950/60 h-0.5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-purple-500 rounded-full"
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
