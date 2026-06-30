"use client";

import React, { useEffect, useRef, useState } from "react";
import { ShieldAlert, AlertTriangle, Cpu, TrendingUp, ShieldCheck } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function ThreatCenter() {
  const { cityState, summary } = useCityStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  // Simulated ML scores
  const [driftIndex, setDriftIndex] = useState(0.02);
  const [isolationScore, setIsolationScore] = useState(0.04);
  const [consensusScore, setConsensusScore] = useState(99.8);

  useEffect(() => {
    // Animate metrics slightly for realism
    const interval = setInterval(() => {
      setDriftIndex(0.01 + Math.random() * 0.03);
      setIsolationScore(0.02 + Math.random() * 0.05);
      setConsensusScore(99.4 + Math.random() * 0.5);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // Animate circular Threat Radar Canvas
  useEffect(() => {
    let raf: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const S = canvas.width;
    const C = S / 2;
    const R = S / 2 - 6;

    const drawRadar = () => {
      ctx.clearRect(0, 0, S, S);

      // Radial rings
      ctx.strokeStyle = "rgba(34, 211, 238, 0.12)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(C, C, R, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(C, C, R * 0.65, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(C, C, R * 0.35, 0, Math.PI * 2); ctx.stroke();

      // Axes
      ctx.beginPath();
      ctx.moveTo(C, 4); ctx.lineTo(C, S - 4);
      ctx.moveTo(4, C); ctx.lineTo(S - 4, C);
      ctx.stroke();

      // Sweeper sweep
      const angle = (Date.now() / 1400) % (Math.PI * 2);
      const gradient = ctx.createRadialGradient(C, C, 0, C, C, R);
      gradient.addColorStop(0, "rgba(34, 211, 238, 0)");
      gradient.addColorStop(1, "rgba(34, 211, 238, 0.15)");

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.moveTo(C, C);
      ctx.arc(C, C, R, angle - 0.3, angle);
      ctx.lineTo(C, C);
      ctx.fill();

      // Sweep line
      ctx.strokeStyle = "rgba(34, 211, 238, 0.4)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(C, C);
      ctx.lineTo(C + Math.cos(angle) * R, C + Math.sin(angle) * R);
      ctx.stroke();

      // Plot active incidents as radar target points
      if (cityState) {
        cityState.emergency.active_incidents.forEach((inc, idx) => {
          const t = (idx * 1.6 + 1.2) % (Math.PI * 2);
          const dist = R * (0.4 + (idx * 0.18) % 0.5);
          const tx = C + Math.cos(t) * dist;
          const ty = C + Math.sin(t) * dist;

          // Flashing target circle
          const blink = 0.4 + Math.sin(Date.now() / 150) * 0.35;
          ctx.fillStyle = `rgba(255, 51, 102, ${blink})`;
          ctx.beginPath(); ctx.arc(tx, ty, 3.5, 0, Math.PI * 2); ctx.fill();

          ctx.strokeStyle = "rgba(255, 51, 102, 0.5)";
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(tx, ty, 8, 0, Math.PI * 2); ctx.stroke();

          ctx.fillStyle = "rgba(255, 51, 102, 0.8)";
          ctx.font = "bold 6px monospace";
          ctx.fillText(`ANOM_A`, tx + 6, ty + 2);
        });
      }

      raf = requestAnimationFrame(drawRadar);
    };

    drawRadar();
    return () => cancelAnimationFrame(raf);
  }, [cityState]);

  // Determine threat text and levels
  const alertCount = summary?.alerts.length ?? 0;
  const isCritical = alertCount > 2;
  const driftScore = isCritical ? 0.38 : driftIndex;
  const isoScore = isCritical ? 0.84 : isolationScore;
  const consensusVal = isCritical ? 92.4 : consensusScore;

  return (
    <div className="h-full flex items-center justify-between p-3 select-none text-slate-300 gap-4">
      {/* Col 1 — Threat Radar Scanner */}
      <div className="flex items-center gap-3 shrink-0 bg-slate-950/40 p-2.5 rounded border border-cyan-500/5 h-full">
        <canvas ref={canvasRef} width={120} height={120} className="bg-slate-950/20 rounded-full shrink-0" />
        
        <div className="font-mono flex flex-col justify-between h-full w-32 py-1">
          <div>
            <span className="text-[7.5px] font-bold text-slate-500 uppercase tracking-widest block">isolation forest</span>
            <span className={`text-base font-bold tracking-wide mt-0.5 block ${isCritical ? "text-red-400" : "text-cyan-300"}`}>
              {isoScore.toFixed(3)}
            </span>
          </div>
          <div>
            <span className="text-[7.5px] font-bold text-slate-500 uppercase tracking-widest block">anomaly consensus</span>
            <span className="text-xs font-bold text-slate-200 mt-0.5 block">
              {consensusVal.toFixed(1)}% SECURE
            </span>
          </div>
        </div>
      </div>

      {/* Col 2 — Security & Behavior Metrics */}
      <div className="flex-1 bg-slate-950/40 p-2.5 rounded border border-cyan-500/5 h-full font-mono text-[9px] flex flex-col justify-between py-2">
        <div className="flex items-center justify-between border-b border-cyan-500/10 pb-1">
          <span className="font-bold text-cyan-300 flex items-center gap-1.5 uppercase">
            <ShieldAlert className="w-3.5 h-3.5" />
            CONSENSUS STATUS
          </span>
          <span className={`text-[8px] font-bold px-1 py-0.5 rounded leading-none ${isCritical ? "bg-red-950 text-red-400 border border-red-500/25" : "bg-cyan-950 text-cyan-400 border border-cyan-500/25"}`}>
            {isCritical ? "ALERT INJECTED" : "NOMINAL ENGINE"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 mt-1">
          <div>
            <span className="text-slate-500 text-[8px] block">MODEL DRIFT</span>
            <strong className="text-slate-300 text-xs">{driftScore.toFixed(4)}</strong>
          </div>
          <div>
            <span className="text-slate-500 text-[8px] block">CONSENSUS RATIO</span>
            <strong className="text-slate-300 text-xs">4 / 4 ONLINE</strong>
          </div>
        </div>

        <div className="border-t border-slate-800 pt-1.5 flex items-center gap-1.5 text-slate-500 text-[8px]">
          <ShieldCheck className="w-3 h-3 text-emerald-400" />
          <span className="uppercase text-slate-400 truncate w-48">Audit root chain fully validated</span>
        </div>
      </div>

      {/* Col 3 — Predictive Forecast Grid */}
      <div className="flex-[1.5] bg-slate-950/40 p-2.5 rounded border border-cyan-500/5 h-full font-mono text-[9px] flex flex-col justify-between py-2">
        <div className="border-b border-cyan-500/10 pb-1 flex items-center gap-1">
          <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-bold text-cyan-300 uppercase">TELEMETRY PREDICTIONS</span>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center mt-1.5">
          <div className="bg-slate-900/40 p-1 border border-cyan-500/5 rounded">
            <span className="text-slate-500 text-[7.5px] block">NEXT 5 MIN</span>
            <span className="text-[10px] text-cyan-300 font-bold block">
              {isCritical ? "CONGESTED" : "NOMINAL"}
            </span>
            <span className="text-[7px] text-slate-500">92% CONF</span>
          </div>
          <div className="bg-slate-900/40 p-1 border border-cyan-500/5 rounded">
            <span className="text-slate-500 text-[7.5px] block">NEXT 10 MIN</span>
            <span className="text-[10px] text-cyan-300 font-bold block">
              {isCritical ? "LOAD SURGE" : "STABLE FLOW"}
            </span>
            <span className="text-[7px] text-slate-500">85% CONF</span>
          </div>
          <div className="bg-slate-900/40 p-1 border border-cyan-500/5 rounded">
            <span className="text-slate-500 text-[7.5px] block">NEXT 1 HOUR</span>
            <span className="text-[10px] text-cyan-300 font-bold block">
              {isCritical ? "PRESSURE STB" : "EQUILIBRIUM"}
            </span>
            <span className="text-[7px] text-slate-500">76% CONF</span>
          </div>
        </div>
      </div>

      {/* Col 4 — Preventive Actions Log */}
      <div className="flex-[1.5] bg-slate-950/40 p-2.5 rounded border border-cyan-500/5 h-full font-mono text-[9px] flex flex-col justify-between py-2">
        <div className="border-b border-cyan-500/10 pb-1 flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span className="font-bold text-cyan-300 uppercase">PREVENTIVE ACTION LOG</span>
        </div>

        <div className="flex-1 overflow-y-auto mt-1.5 space-y-1 text-[8.5px] leading-tight text-slate-400">
          {isCritical ? (
            <>
              <div className="flex items-center gap-1 text-red-400">
                <span className="w-1 h-1 rounded-full bg-red-400 animate-pulse" />
                ENFORCE SUBSTATION STATIC LOAD LIMITS
              </div>
              <div className="flex items-center gap-1 text-amber-400">
                <span className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" />
                PREEMPT MEDICAL LINK GREEN TIMING
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-1 text-emerald-400">
                <span className="w-1 h-1 rounded-full bg-emerald-400" />
                MONITORING SYSTEM ENVELOPE: NOMINAL
              </div>
              <div className="flex items-center gap-1 text-slate-500">
                <span className="w-1 h-1 rounded-full bg-slate-600" />
                AUTOMATED REGULATORY LOOPS BALANCED
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
export default ThreatCenter;
