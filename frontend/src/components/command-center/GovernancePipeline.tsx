"use client";

import React, { useEffect, useState } from "react";
import { GitCommit, CheckCircle, ShieldAlert, Cpu } from "lucide-react";
import { useCityStore } from "@/store/city-store";

interface PipelineStep {
  key: string;
  label: string;
  desc: string;
}

const STEPS: PipelineStep[] = [
  { key: "init", label: "AGENT INIT", desc: "Instantiating model telemetry query" },
  { key: "policy", label: "POLICY CHECK", desc: "Evaluating regulatory zoning policies" },
  { key: "constraint", label: "CONSTRAINTS", desc: "Verifying physical system boundary limits" },
  { key: "risk", label: "RISK ASSESSMENT", desc: "Calculating systemic risk coefficients" },
  { key: "conflict", label: "CONFLICT RESOLVE", desc: "Negotiating shared infrastructure locks" },
  { key: "armoriq", label: "ARMORIQ SHIELD", desc: "Validating transaction authorization key" },
  { key: "human", label: "HUMAN OVERSIGHT", desc: "Awaiting operator policy confirmation" },
  { key: "exec", label: "EXECUTE ACTION", desc: "Sending signals to physical relays" },
  { key: "hash", label: "HASH GENERATE", desc: "Hashing parameters with SHA-256" },
  { key: "merkle", label: "MERKLE LEAF", desc: "Appending node block to local tree" },
  { key: "audit", label: "AUDIT LEDGER", desc: "Sealing block into MongoDB Ledger" },
  { key: "twin", label: "TWIN UPDATE", desc: "Pushing state vector updates to Twin" },
];

export function GovernancePipeline() {
  const { liveEvents } = useCityStore();
  const [activeStep, setActiveStep] = useState(0);

  // Auto-traverse gates for visual telemetry
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((s) => (s + 1) % STEPS.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const activeOp = STEPS[activeStep] ?? STEPS[0];

  return (
    <div className="h-full flex flex-col overflow-hidden bg-slate-950/20">
      {/* Title Header */}
      <div className="px-3 py-1.5 border-b border-cyan-500/10 bg-slate-950/50 shrink-0 flex items-center justify-between">
        <span className="text-[9px] tracking-[0.15em] font-mono text-cyan-400 font-bold flex items-center gap-1">
          <GitCommit className="w-3 h-3 text-cyan-400" />
          GOVERNANCE DECISION PIPELINE
        </span>
        <span className="text-[7.5px] font-mono text-emerald-400 font-bold tracking-wider animate-pulse flex items-center gap-1 uppercase">
          <span className="w-1 h-1 rounded-full bg-emerald-400" />
          flow operational
        </span>
      </div>

      {/* Active Gate Operation Details */}
      <div className="px-3 py-1 bg-slate-900/35 border-b border-cyan-500/5 shrink-0 flex items-center justify-between font-mono text-[8px]">
        <div className="flex items-center gap-1.5 text-cyan-300 font-bold">
          <Cpu className="w-2.5 h-2.5 text-cyan-400 animate-spin-slow" />
          <span>GATE {String(activeStep + 1).padStart(2, "0")}: {activeOp?.label}</span>
        </div>
        <span className="text-slate-500 truncate max-w-[170px] uppercase font-bold text-right">
          {activeOp?.desc}
        </span>
      </div>

      {/* Horizontal Pipeline flow slider */}
      <div className="flex-1 flex items-center overflow-x-auto px-3 gap-1 relative min-h-[48px] bg-slate-950/10">
        {STEPS.map((step, i) => {
          let cls = "bg-slate-900 border-slate-800 text-slate-600";
          let icon = <GitCommit className="w-2.5 h-2.5 text-slate-700" />;

          const isActive = i === activeStep;
          const isSuccess = i < activeStep;

          if (isActive) {
            cls = "bg-cyan-950/40 border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(34,211,238,0.15)] font-bold";
            icon = (
              <span className="relative w-2.5 h-2.5 flex items-center justify-center">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping absolute" />
                <span className="w-1 h-1 rounded-full bg-cyan-400" />
              </span>
            );
          } else if (isSuccess) {
            cls = "bg-emerald-950/20 border-emerald-500/40 text-emerald-400 font-medium";
            icon = <CheckCircle className="w-2.5 h-2.5 text-emerald-400" />;
          }

          // Check if latest event represents failure at this node
          const latest = liveEvents[0];
          if (latest) {
            const type = latest.event_type?.toLowerCase() ?? "";
            if (type.includes("failed") || type.includes("unauthorized") || type.includes("blocked")) {
              if (step.key === "armoriq" && type.includes("unauthorized") && isActive) {
                cls = "bg-red-950/40 border-red-500 text-red-400 font-bold shadow-[0_0_8px_rgba(239,68,68,0.2)]";
                icon = <ShieldAlert className="w-2.5 h-2.5 text-red-500" />;
              } else if (step.key === "exec" && type.includes("failed") && isActive) {
                cls = "bg-red-950/40 border-red-500 text-red-400 font-bold shadow-[0_0_8px_rgba(239,68,68,0.2)]";
                icon = <ShieldAlert className="w-2.5 h-2.5 text-red-500" />;
              }
            }
          }

          return (
            <React.Fragment key={step.key}>
              <div
                className={`shrink-0 px-2 py-1 rounded border flex items-center gap-1.5 font-mono text-[7px] tracking-wider transition-all duration-350 select-none ${cls}`}
              >
                {icon}
                {step.label}
              </div>

              {/* Connecting wire with glowing slider pulse */}
              {i < STEPS.length - 1 && (
                <div className="w-4 h-0.5 bg-slate-900 shrink-0 relative overflow-hidden rounded">
                  <div
                    className={`h-full absolute left-0 right-0 transition-colors duration-350 ${
                      isSuccess ? "bg-emerald-500/30" : "bg-transparent"
                    }`}
                  />
                  {isActive && (
                    <span className="w-1.5 h-full bg-cyan-400 rounded absolute left-0 animate-pipeline-flow shadow-[0_0_4px_#22d3ee]" />
                  )}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
