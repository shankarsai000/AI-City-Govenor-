"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  Activity,
  Fingerprint,
  Lock,
  Unlock,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  TrendingUp,
  Cpu,
  Brain,
  Layers,
  Clock
} from "lucide-react";
import { useCityStore } from "@/store/city-store";
import { DecisionGraphRecord } from "@/lib/api";

// ── Fallback Demo Decisions ─────────────────────────────────────────
const DEMO_DECISIONS: DecisionGraphRecord[] = [
  {
    id: "dg-1",
    action_id: "ac-101",
    agent_id: "traffic-agent",
    agent_name: "Traffic AI",
    domain: "traffic",
    action_type: "emergency_preemption",
    policies_applied: [
      { policy_name: "Emergency Priority Transit", rule_type: "allow", matched: true, details: { priority: "highest" } },
      { policy_name: "Conflict Intersect Lock", rule_type: "constrain", matched: true, details: { locked: "I-2" } }
    ],
    risk_assessment: {
      risk_level: "low",
      requires_human: false,
      details: { impact_score: 0.12 }
    },
    armoriq_decision: {
      status: "authorized",
      authorized: true,
      details: { signature_verified: true }
    },
    ml_assessment: {
      is_anomalous: false,
      anomaly_score: 0.045,
      confidence: 0.98,
      top_features: []
    },
    human_approval: null,
    execution_result: {
      status: "success",
      result: { corridor_preempted: "Medical Avenue", phase: "green-wave" }
    },
    created_at: new Date(Date.now() - 5000).toISOString()
  },
  {
    id: "dg-2",
    action_id: "ac-102",
    agent_id: "power-agent",
    agent_name: "Power AI",
    domain: "power",
    action_type: "shed_load",
    policies_applied: [
      { policy_name: "Hospital Power Preservation", rule_type: "deny", matched: true, details: { protected: "Central Medical" } },
      { policy_name: "Grid Load Leveling", rule_type: "allow", matched: true, details: { amount_mw: 15 } }
    ],
    risk_assessment: {
      risk_level: "high",
      requires_human: true,
      details: { reason: "Substation load shedding near high-risk medical zone" }
    },
    armoriq_decision: {
      status: "blocked",
      authorized: false,
      details: { violation: "Hospital Power Protection Policy breached" }
    },
    ml_assessment: {
      is_anomalous: true,
      anomaly_score: 0.82,
      confidence: 0.91,
      top_features: []
    },
    human_approval: {
      approval_id: "app-302",
      decision: "denied",
      reason: "Rejected: Critical medical infrastructure backup load cannot be shed"
    },
    execution_result: null,
    created_at: new Date(Date.now() - 25000).toISOString()
  }
];

export function ArmorIQDashboard() {
  const { decisionGraphs, demoMode, setDemoMode } = useCityStore();
  const [activeIdx, setActiveIdx] = useState(0);
  const [activeStep, setActiveStep] = useState(0);

  // Merge server decision graphs with fallback demos to guarantee robust visual feedback
  const list = decisionGraphs && decisionGraphs.length > 0 ? decisionGraphs : DEMO_DECISIONS;
  const current = list[activeIdx] ?? list[0] ?? DEMO_DECISIONS[0];

  // Particle tracking variables
  const [msgPulse, setMsgPulse] = useState<{ from: string; to: string; type: string } | null>(null);

  useEffect(() => {
    setActiveStep(0);
    const maxSteps = demoMode === "with" ? 9 : 7;
    let step = 0;
    const timer = setInterval(() => {
      if (step < maxSteps) {
        step++;
        setActiveStep(step);
      } else {
        clearInterval(timer);
      }
    }, 500);
    return () => clearInterval(timer);
  }, [demoMode]);

  useEffect(() => {
    // Periodically simulate messaging pulses between agents and ArmorIQ
    const interval = setInterval(() => {
      const paths = [
        { from: "traffic", to: "armoriq", type: "request" },
        { from: "armoriq", to: "power", type: "negotiate" },
        { from: "power", to: "armoriq", type: "approve" },
        { from: "armoriq", to: "traffic", type: "seal" },
        { from: "emergency", to: "armoriq", type: "request" },
        { from: "armoriq", to: "water", type: "lock" }
      ];
      const randomPath = paths[Math.floor(Math.random() * paths.length)]!;
      setMsgPulse(randomPath);
      setTimeout(() => setMsgPulse(null), 1800);
    }, 4500);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="absolute inset-0 bg-slate-950 flex font-mono select-none overflow-y-auto p-4 gap-4 text-slate-300">
      {/* ── LEFT SECTION: ArmorIQ Status & Collaboration Graph ── */}
      <div className="flex-[2.5] min-w-0 flex flex-col gap-4">
        {/* Core Dedicated Centerpiece */}
        <div className="p-4 rounded border border-cyan-500/10 bg-slate-900/30 backdrop-blur flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-cyan-500/10 pb-2">
            <span className="text-xs font-bold text-cyan-400 tracking-wider flex items-center gap-1.5 uppercase">
              <Shield className="w-4 h-4 text-cyan-400 animate-pulse" />
              ARMORIQ CORE ENGINE
            </span>
            <span className="text-[9px] px-2 py-0.5 rounded font-bold bg-emerald-950/40 border border-emerald-500/35 text-emerald-400">
              ACTIVE ENFORCEMENT
            </span>
          </div>

          <div className="flex items-center gap-4 py-1">
            {/* Trust Meter (SVG Radial Ring) */}
            <div className="relative w-18 h-18 shrink-0 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90">
                <circle cx="36" cy="36" r="30" stroke="rgba(34, 211, 238, 0.05)" strokeWidth="4" fill="transparent" />
                <circle
                  cx="36"
                  cy="36"
                  r="30"
                  stroke="#22d3ee"
                  strokeWidth="4"
                  fill="transparent"
                  strokeDasharray="188.4"
                  strokeDashoffset={188.4 - (188.4 * 0.986)}
                  className="transition-all duration-1000"
                />
              </svg>
              <div className="absolute flex flex-col items-center justify-center text-center">
                <span className="text-[11px] font-bold text-slate-200">98.6%</span>
                <span className="text-[6px] text-slate-500 leading-none">TRUST</span>
              </div>
            </div>

            <div className="flex-1 grid grid-cols-2 gap-2 text-[9px]">
              <div>
                <span className="text-slate-500 block">LEDGER STATUS</span>
                <span className="font-bold text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> SECURED
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">CONSENSUS RATIO</span>
                <span className="font-bold text-slate-200">4 / 4 VALID</span>
              </div>
              <div>
                <span className="text-slate-500 block">SIGNING ALGORITHM</span>
                <span className="font-bold text-slate-300">RS256 (2048-BIT)</span>
              </div>
              <div>
                <span className="text-slate-500 block">ENVELOPE LATENCY</span>
                <span className="font-bold text-cyan-300">1.84ms AVG</span>
              </div>
            </div>
          </div>

          {/* Cryptographic Seal & Hash info */}
          <div className="bg-slate-950/60 p-2 rounded border border-cyan-500/5 text-[8.5px]">
            <div className="flex items-center justify-between text-slate-400 pb-1 border-b border-slate-900">
              <span className="flex items-center gap-1"><Fingerprint className="w-3 h-3 text-cyan-500" /> SECURED LEDGER ENTRY</span>
              <span className="text-[7.5px] text-slate-500">ROOT SEAL</span>
            </div>
            <div className="mt-1.5 font-bold space-y-0.5">
              <div className="truncate text-cyan-400">MERKLE ROOT: <span className="text-slate-300">f20cb84e72a8cb71ea8640192bcde57d...</span></div>
              <div className="truncate text-cyan-400">SIGNATURE: <span className="text-slate-300">SHA256withRSA_8b211a7aef2cb3902196bc...</span></div>
            </div>
          </div>
        </div>

        {/* Live Agent Collaboration interaction graph — ArmorIQ is KING */}
        <div className="p-4 rounded border border-cyan-500/10 bg-slate-900/30 backdrop-blur flex-1 flex flex-col gap-2 relative min-h-[220px]">
          <span className="text-xs font-bold text-cyan-400 tracking-wider flex items-center gap-1.5 uppercase border-b border-cyan-500/10 pb-2">
            <Brain className="w-4 h-4 text-cyan-400" />
            LIVE AGENT INTERACTION GRAPH
            <span className="ml-auto text-[7.5px] text-emerald-400 font-bold animate-pulse">● ALL CHANNELS GOVERNED</span>
          </span>

          {/* SVG Canvas — ArmorIQ dominates center */}
          <div className="flex-1 w-full relative overflow-hidden bg-slate-950/40 rounded border border-cyan-500/5">
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 400 200" preserveAspectRatio="xMidYMid meet">
              <defs>
                {/* Glowing line gradient */}
                <radialGradient id="armoriq-glow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgba(34, 211, 238, 0.3)" />
                  <stop offset="50%" stopColor="rgba(34, 211, 238, 0.08)" />
                  <stop offset="100%" stopColor="rgba(34, 211, 238, 0)" />
                </radialGradient>
                <radialGradient id="armoriq-core-glow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgba(34, 211, 238, 0.15)" />
                  <stop offset="100%" stopColor="rgba(34, 211, 238, 0)" />
                </radialGradient>
                {/* Animated line gradients for each agent */}
                <linearGradient id="line-traffic" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="rgba(34, 211, 238, 0.5)"><animate attributeName="stopColor" values="rgba(34,211,238,0.5);rgba(34,211,238,0.15);rgba(34,211,238,0.5)" dur="2s" repeatCount="indefinite"/></stop>
                  <stop offset="100%" stopColor="rgba(34, 211, 238, 0.08)" />
                </linearGradient>
                <linearGradient id="line-power" x1="100%" y1="0%" x2="0%" y2="0%">
                  <stop offset="0%" stopColor="rgba(168, 85, 247, 0.5)"><animate attributeName="stopColor" values="rgba(168,85,247,0.5);rgba(168,85,247,0.15);rgba(168,85,247,0.5)" dur="2.3s" repeatCount="indefinite"/></stop>
                  <stop offset="100%" stopColor="rgba(168, 85, 247, 0.08)" />
                </linearGradient>
                <linearGradient id="line-emergency" x1="0%" y1="100%" x2="0%" y2="0%">
                  <stop offset="0%" stopColor="rgba(244, 63, 94, 0.5)"><animate attributeName="stopColor" values="rgba(244,63,94,0.5);rgba(244,63,94,0.15);rgba(244,63,94,0.5)" dur="1.8s" repeatCount="indefinite"/></stop>
                  <stop offset="100%" stopColor="rgba(244, 63, 94, 0.08)" />
                </linearGradient>
                <linearGradient id="line-water" x1="100%" y1="100%" x2="0%" y2="0%">
                  <stop offset="0%" stopColor="rgba(59, 130, 246, 0.5)"><animate attributeName="stopColor" values="rgba(59,130,246,0.5);rgba(59,130,246,0.15);rgba(59,130,246,0.5)" dur="2.6s" repeatCount="indefinite"/></stop>
                  <stop offset="100%" stopColor="rgba(59, 130, 246, 0.08)" />
                </linearGradient>
              </defs>

              {/* Background ambient glow behind ArmorIQ */}
              <circle cx="200" cy="100" r="80" fill="url(#armoriq-glow)" />
              <circle cx="200" cy="100" r="55" fill="url(#armoriq-core-glow)" />

              {/* Orbital ring 1 — outer ring (agents sit on this) */}
              <circle cx="200" cy="100" r="75" fill="none" stroke="rgba(34, 211, 238, 0.06)" strokeWidth="1" strokeDasharray="4 6" >
                <animateTransform attributeName="transform" type="rotate" from="0 200 100" to="360 200 100" dur="60s" repeatCount="indefinite"/>
              </circle>
              {/* Orbital ring 2 — inner pulsing ring */}
              <circle cx="200" cy="100" r="50" fill="none" stroke="rgba(34, 211, 238, 0.1)" strokeWidth="0.8" strokeDasharray="2 4">
                <animateTransform attributeName="transform" type="rotate" from="360 200 100" to="0 200 100" dur="40s" repeatCount="indefinite"/>
              </circle>
              {/* Orbital ring 3 — core breathing ring */}
              <circle cx="200" cy="100" r="30" fill="none" stroke="rgba(34, 211, 238, 0.15)" strokeWidth="1.5">
                <animate attributeName="r" values="28;32;28" dur="3s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" repeatCount="indefinite"/>
              </circle>

              {/* Connection lines — thick glowing beams to ArmorIQ */}
              <line x1="65" y1="42" x2="175" y2="90" stroke="url(#line-traffic)" strokeWidth="2" />
              <line x1="335" y1="42" x2="225" y2="90" stroke="url(#line-power)" strokeWidth="2" />
              <line x1="65" y1="158" x2="175" y2="110" stroke="url(#line-emergency)" strokeWidth="2" />
              <line x1="335" y1="158" x2="225" y2="110" stroke="url(#line-water)" strokeWidth="2" />

              {/* Continuous data particles flowing TO ArmorIQ — always running */}
              {/* Traffic → ArmorIQ */}
              <circle r="3" fill="#22d3ee" opacity="0.9">
                <animateMotion path="M 65,42 L 185,93" dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.3;0.9" dur="2s" repeatCount="indefinite"/>
              </circle>
              <circle r="2" fill="#22d3ee" opacity="0.5">
                <animateMotion path="M 65,42 L 185,93" dur="2s" begin="1s" repeatCount="indefinite" />
              </circle>
              {/* Power → ArmorIQ */}
              <circle r="3" fill="#a855f7" opacity="0.9">
                <animateMotion path="M 335,42 L 215,93" dur="2.3s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.3;0.9" dur="2.3s" repeatCount="indefinite"/>
              </circle>
              <circle r="2" fill="#a855f7" opacity="0.5">
                <animateMotion path="M 335,42 L 215,93" dur="2.3s" begin="1.15s" repeatCount="indefinite" />
              </circle>
              {/* Emergency → ArmorIQ */}
              <circle r="3" fill="#f43f5e" opacity="0.9">
                <animateMotion path="M 65,158 L 185,107" dur="1.8s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.3;0.9" dur="1.8s" repeatCount="indefinite"/>
              </circle>
              <circle r="2" fill="#f43f5e" opacity="0.5">
                <animateMotion path="M 65,158 L 185,107" dur="1.8s" begin="0.9s" repeatCount="indefinite" />
              </circle>
              {/* Water → ArmorIQ */}
              <circle r="3" fill="#3b82f6" opacity="0.9">
                <animateMotion path="M 335,158 L 215,107" dur="2.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.3;0.9" dur="2.6s" repeatCount="indefinite"/>
              </circle>
              <circle r="2" fill="#3b82f6" opacity="0.5">
                <animateMotion path="M 335,158 L 215,107" dur="2.6s" begin="1.3s" repeatCount="indefinite" />
              </circle>

              {/* ArmorIQ response pulses flowing BACK to agents */}
              <circle r="2.5" fill="#10b981" opacity="0.7">
                <animateMotion path="M 185,93 L 65,42" dur="2.5s" begin="0.5s" repeatCount="indefinite" />
              </circle>
              <circle r="2.5" fill="#10b981" opacity="0.7">
                <animateMotion path="M 215,93 L 335,42" dur="2.8s" begin="0.7s" repeatCount="indefinite" />
              </circle>
              <circle r="2.5" fill="#10b981" opacity="0.7">
                <animateMotion path="M 185,107 L 65,158" dur="2.2s" begin="0.3s" repeatCount="indefinite" />
              </circle>
              <circle r="2.5" fill="#10b981" opacity="0.7">
                <animateMotion path="M 215,107 L 335,158" dur="3s" begin="1s" repeatCount="indefinite" />
              </circle>

              {/* Active message pulse overlay (event-driven) */}
              {msgPulse && (
                <circle r="5" fill={
                  msgPulse.type === "request" ? "#22d3ee" :
                  msgPulse.type === "negotiate" ? "#a855f7" :
                  msgPulse.type === "approve" ? "#10b981" :
                  msgPulse.type === "seal" ? "#f59e0b" : "#3b82f6"
                } opacity="0.95">
                  <animateMotion
                    path={
                      msgPulse.from === "traffic" ? "M 65,42 L 200,100" :
                      msgPulse.from === "power" ? "M 335,42 L 200,100" :
                      msgPulse.from === "emergency" ? "M 65,158 L 200,100" :
                      msgPulse.from === "water" ? "M 335,158 L 200,100" :
                      msgPulse.to === "traffic" ? "M 200,100 L 65,42" :
                      msgPulse.to === "power" ? "M 200,100 L 335,42" :
                      msgPulse.to === "water" ? "M 200,100 L 335,158" :
                      "M 200,100 L 65,158"
                    }
                    dur="1.2s" repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* ═══ ARMORIQ CENTER NODE — THE KING ═══ */}
              {/* Outer glow ring */}
              <circle cx="200" cy="100" r="24" fill="rgba(2, 6, 23, 0.9)" stroke="rgba(34, 211, 238, 0.5)" strokeWidth="2">
                <animate attributeName="stroke-opacity" values="0.3;0.7;0.3" dur="2s" repeatCount="indefinite"/>
              </circle>
              {/* Inner bright ring */}
              <circle cx="200" cy="100" r="20" fill="rgba(8, 47, 73, 0.7)" stroke="#22d3ee" strokeWidth="1.5">
                <animate attributeName="stroke-width" values="1.5;2.5;1.5" dur="2.5s" repeatCount="indefinite"/>
              </circle>
              {/* Shield icon background */}
              <circle cx="200" cy="100" r="14" fill="rgba(34, 211, 238, 0.08)" />
              {/* Shield icon path (simplified) */}
              <g transform="translate(192, 89)">
                <path d="M8 1 L14 4 L14 10 C14 14 8 17 8 17 C8 17 2 14 2 10 L2 4 Z" fill="none" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <animate attributeName="stroke" values="#22d3ee;#10b981;#22d3ee" dur="4s" repeatCount="indefinite"/>
                </path>
                <path d="M5.5 9 L7 10.5 L10.5 7" fill="none" stroke="#10b981" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
              </g>
              {/* ArmorIQ label */}
              <text x="200" y="120" textAnchor="middle" fill="#22d3ee" fontSize="6" fontWeight="900" fontFamily="monospace" letterSpacing="1.5">ARMORIQ</text>
              <text x="200" y="128" textAnchor="middle" fill="rgba(34, 211, 238, 0.45)" fontSize="4" fontWeight="700" fontFamily="monospace" letterSpacing="0.8">GOVERNING ALL AGENTS</text>

              {/* ═══ AGENT NODES — subordinate satellites ═══ */}
              {/* Traffic Agent — top-left */}
              <circle cx="65" cy="42" r="14" fill="rgba(2, 6, 23, 0.85)" stroke="rgba(34, 211, 238, 0.2)" strokeWidth="1" />
              <text x="65" y="40" textAnchor="middle" fill="#67e8f9" fontSize="8" fontFamily="monospace">⚡</text>
              <text x="65" y="50" textAnchor="middle" fill="rgba(148, 163, 184, 0.7)" fontSize="5" fontWeight="700" fontFamily="monospace">TRAFFIC</text>

              {/* Power Agent — top-right */}
              <circle cx="335" cy="42" r="14" fill="rgba(2, 6, 23, 0.85)" stroke="rgba(168, 85, 247, 0.2)" strokeWidth="1" />
              <text x="335" y="40" textAnchor="middle" fill="#c084fc" fontSize="8" fontFamily="monospace">⚙</text>
              <text x="335" y="50" textAnchor="middle" fill="rgba(148, 163, 184, 0.7)" fontSize="5" fontWeight="700" fontFamily="monospace">POWER</text>

              {/* Emergency Agent — bottom-left */}
              <circle cx="65" cy="158" r="14" fill="rgba(2, 6, 23, 0.85)" stroke="rgba(244, 63, 94, 0.2)" strokeWidth="1" />
              <text x="65" y="156" textAnchor="middle" fill="#fb7185" fontSize="8" fontFamily="monospace">🚨</text>
              <text x="65" y="166" textAnchor="middle" fill="rgba(148, 163, 184, 0.7)" fontSize="5" fontWeight="700" fontFamily="monospace">EMERGENCY</text>

              {/* Water Agent — bottom-right */}
              <circle cx="335" cy="158" r="14" fill="rgba(2, 6, 23, 0.85)" stroke="rgba(59, 130, 246, 0.2)" strokeWidth="1" />
              <text x="335" y="156" textAnchor="middle" fill="#60a5fa" fontSize="8" fontFamily="monospace">💧</text>
              <text x="335" y="166" textAnchor="middle" fill="rgba(148, 163, 184, 0.7)" fontSize="5" fontWeight="700" fontFamily="monospace">WATER</text>

              {/* Live throughput counters near connection lines */}
              <text x="120" y="60" textAnchor="middle" fill="rgba(34, 211, 238, 0.4)" fontSize="4" fontFamily="monospace">42 req/s</text>
              <text x="280" y="60" textAnchor="middle" fill="rgba(168, 85, 247, 0.4)" fontSize="4" fontFamily="monospace">38 req/s</text>
              <text x="120" y="142" textAnchor="middle" fill="rgba(244, 63, 94, 0.4)" fontSize="4" fontFamily="monospace">27 req/s</text>
              <text x="280" y="142" textAnchor="middle" fill="rgba(59, 130, 246, 0.4)" fontSize="4" fontFamily="monospace">31 req/s</text>
            </svg>
          </div>
        </div>
      </div>

      {/* ── RIGHT SECTION: Sequential Gate flow & Explainable AI logs ── */}
      <div className="flex-[3.5] min-w-0 flex flex-col gap-4">
        {/* Verification flow gates */}
        <div className="p-4 rounded border border-cyan-500/10 bg-slate-900/30 backdrop-blur flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-cyan-500/10 pb-2">
            <span className="text-xs font-bold text-cyan-400 tracking-wider flex items-center gap-1.5 uppercase">
              <Activity className="w-4 h-4 text-cyan-400" />
              ARMORIQ SEQUENTIAL VERIFICATION FLOW
            </span>
            <span className="text-[8.5px] font-mono text-slate-400">
              ACTION: <strong className="text-cyan-300 font-bold uppercase">{current.action_type.replace("_", " ")}</strong>
            </span>
          </div>

          <div className="grid grid-cols-4 gap-1.5">
            {[
              { label: "1. AI INTENT", time: "0.2ms", status: "PASS" },
              { label: "2. CAPABILITY", time: "0.4ms", status: "PASS" },
              { label: "3. ROLE AUTH", time: "0.2ms", status: "PASS" },
              { label: "4. POLICY SET", time: "0.6ms", status: current.armoriq_decision.authorized ? "PASS" : "BLOCKED" },
              { label: "5. CONSTRAINT", time: "0.8ms", status: current.armoriq_decision.authorized ? "PASS" : "WARNING" },
              { label: "6. LOCK SYNC", time: "0.5ms", status: "PASS" },
              { label: "7. ANOMALY ML", time: "1.2ms", status: current.ml_assessment?.is_anomalous ? "WARNING" : "PASS" },
              { label: "8. RISK SCORE", time: "0.7ms", status: current.risk_assessment.risk_level === "high" ? "WARNING" : "PASS" },
              { label: "9. DECISION", time: "0.4ms", status: current.armoriq_decision.authorized ? "PASS" : "BLOCKED" },
              { label: "10. RSA SIGN", time: "1.1ms", status: "PASS" },
              { label: "11. MERKLE LEAF", time: "0.5ms", status: "PASS" },
              { label: "12. TWIN UPDATE", time: "1.4ms", status: current.armoriq_decision.authorized ? "PASS" : "BLOCKED" }
            ].map((gate) => {
              const bg = gate.status === "PASS" ? "bg-emerald-950/20 border-emerald-500/20 text-emerald-400" :
                         gate.status === "WARNING" ? "bg-amber-950/20 border-amber-500/20 text-amber-400" :
                         "bg-red-950/20 border-red-500/20 text-red-400";
              return (
                <div key={gate.label} className={`p-1.5 rounded border text-[7.5px] flex flex-col justify-between h-9 ${bg}`}>
                  <span className="font-bold">{gate.label}</span>
                  <div className="flex items-center justify-between text-[7px] opacity-75 mt-0.5">
                    <span>{gate.time}</span>
                    <span className="font-bold">{gate.status}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Explainable AI & Value Showcase */}
        <div className="flex-1 flex gap-4 min-h-0">
          {/* Explainable AI Card */}
          <div className="flex-1 p-4 rounded border border-cyan-500/10 bg-slate-900/30 backdrop-blur flex flex-col gap-2.5 overflow-hidden">
            <span className="text-xs font-bold text-cyan-400 tracking-wider flex items-center gap-1.5 uppercase border-b border-cyan-500/10 pb-2">
              <FileText className="w-4 h-4 text-cyan-400" />
              EXPLAINABLE GOVERNANCE
            </span>

            <div className="flex-1 overflow-y-auto text-[8.5px] space-y-2 pr-1">
              <div>
                <span className="text-slate-500 block">PROPOSAL OBJECTIVE:</span>
                <p className="text-slate-300 font-bold leading-normal">
                  {current.domain === "traffic"
                    ? "Establish green-wave signal preemption corridor along Main Boulevard to resolve emergency dispatch congestion."
                    : "Initiate load shedding cycles across Sector 3 grid segments to balance peak loading coefficients."}
                </p>
              </div>

              <div>
                <span className="text-slate-500 block">EVALUATED RULES & CONSTRAINTS:</span>
                <ul className="list-disc pl-3 text-slate-400 space-y-0.5 mt-0.5">
                  {current.policies_applied.map((p, idx) => (
                    <li key={idx} className={p.matched ? "text-cyan-300" : "text-slate-400"}>
                      {p.policy_name} ({p.rule_type.toUpperCase()}) - {p.matched ? "MATCHED" : "NOMINAL"}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <span className="text-slate-500 block">ARMORIQ TRUST RATIONALE:</span>
                <p className={`p-1.5 rounded leading-normal border ${
                  current.armoriq_decision.authorized
                    ? "bg-emerald-950/20 border-emerald-500/10 text-emerald-400"
                    : "bg-red-950/20 border-red-500/10 text-red-400"
                }`}>
                  {current.armoriq_decision.authorized
                    ? "APPROVED: Action validation successful. Cryptographic keys and capabilities matched. System boundaries preserved."
                    : `BLOCKED: Policy violation detected. Reason: ${current.armoriq_decision.details.violation ?? "unauthorized operation"}.`}
                </p>
              </div>
            </div>
          </div>

          {/* Value Showcase Comparison */}
          <div className="flex-1 p-4 rounded border border-cyan-500/10 bg-slate-900/30 backdrop-blur flex flex-col gap-2.5 overflow-hidden">
            <span className="text-xs font-bold text-cyan-400 tracking-wider flex items-center gap-1.5 uppercase border-b border-cyan-500/10 pb-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              ARMORIQ COMPARATIVE SHIELD
            </span>

            {/* Toggle bar */}
            <div className="flex gap-1.5 p-1 bg-slate-950/80 rounded border border-cyan-500/5 select-none shrink-0">
              <button
                onClick={() => setDemoMode("with")}
                className={`flex-1 text-[8px] font-bold py-1 px-1.5 rounded transition ${
                  demoMode === "with"
                    ? "bg-emerald-950/50 border border-emerald-500/30 text-emerald-400 font-extrabold shadow-md"
                    : "text-slate-500 border border-transparent hover:text-slate-400"
                }`}
              >
                WITH ARMORIQ
              </button>
              <button
                onClick={() => setDemoMode("without")}
                className={`flex-1 text-[8px] font-bold py-1 px-1.5 rounded transition ${
                  demoMode === "without"
                    ? "bg-red-950/50 border border-red-500/30 text-red-400 font-extrabold shadow-md animate-pulse"
                    : "text-slate-500 border border-transparent hover:text-slate-400"
                }`}
              >
                WITHOUT ARMORIQ
              </button>
            </div>

            {/* Simulated Animated Path Flow */}
            <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-1 select-none font-mono text-[8px]">
              {demoMode === "without" ? (
                <>
                  {[
                    "Traffic AI (Unauthorized Action)",
                    "Attempt Unauthorized Power Access",
                    "Power Grid Shutdown (0 MW Load)",
                    "Emergency Escalation",
                    "City Health Drops to 18%",
                    "Infrastructure Failure",
                    "No Audit & Traceability Void"
                  ].map((step, idx) => {
                    const isVisible = idx <= activeStep;
                    return (
                      <div key={idx} className="flex flex-col items-center">
                        {idx > 0 && (
                          <div className={`w-0.5 h-3 border-l ${isVisible ? "border-red-500 animate-pulse" : "border-slate-800"}`} />
                        )}
                        <div
                          className={`w-full p-1.5 rounded border text-center transition-all duration-300 ${
                            isVisible
                              ? "bg-red-950/25 border-red-500/40 text-red-400 font-bold"
                              : "bg-slate-950/20 border-slate-900 text-slate-600"
                          }`}
                        >
                          {step}
                        </div>
                      </div>
                    );
                  })}
                </>
              ) : (
                <>
                  {[
                    "Traffic AI",
                    "ArmorIQ Authorization check",
                    "Capability Validation ✓",
                    "Policy Validation ✓",
                    "Constraint Check ✓",
                    "Risk Analysis ✓",
                    "Action Blocked / Governed",
                    "Immutable Audit Created",
                    "Infrastructure Protected"
                  ].map((step, idx) => {
                    const isVisible = idx <= activeStep;
                    return (
                      <div key={idx} className="flex flex-col items-center">
                        {idx > 0 && (
                          <div className={`w-0.5 h-3 border-l ${isVisible ? "border-emerald-500" : "border-slate-800"}`} />
                        )}
                        <div
                          className={`w-full p-1.5 rounded border text-center transition-all duration-300 ${
                            isVisible
                              ? "bg-emerald-950/25 border-emerald-500/40 text-emerald-400 font-bold"
                              : "bg-slate-950/20 border-slate-900 text-slate-600"
                          }`}
                        >
                          {step}
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ArmorIQDashboard;
