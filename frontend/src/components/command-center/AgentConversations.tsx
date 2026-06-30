"use client";

import React, { useEffect, useRef } from "react";
import { ArrowRight, ShieldCheck, ShieldAlert, Lock, Unlock } from "lucide-react";
import { useCityStore } from "@/store/city-store";

/** Color-coded message types for ArmorIQ mediation visibility */
function getMsgStyle(message: string, sender: string, demoMode: string) {
  const lower = message.toLowerCase();
  const isSys = sender === "System Console";

  if (demoMode === "without") {
    if (lower.includes("unauthorized") || lower.includes("bypass") || lower.includes("failed"))
      return { bg: "bg-red-950/30 border-red-500/20", text: "text-red-400", badge: "BLOCKED", badgeCls: "bg-red-950/40 border-red-500/30 text-red-400" };
    return { bg: "bg-slate-900/30 border-red-500/5", text: "text-slate-400", badge: null, badgeCls: "" };
  }

  if (lower.includes("approved") || lower.includes("authorized") || lower.includes("validated"))
    return { bg: "bg-emerald-950/15 border-emerald-500/10", text: "text-emerald-400", badge: "APPROVED", badgeCls: "bg-emerald-950/40 border-emerald-500/30 text-emerald-400" };
  if (lower.includes("negotiat") || lower.includes("capability") || lower.includes("handshake"))
    return { bg: "bg-purple-950/15 border-purple-500/10", text: "text-purple-400", badge: "NEGOTIATE", badgeCls: "bg-purple-950/40 border-purple-500/30 text-purple-400" };
  if (lower.includes("blocked") || lower.includes("denied") || lower.includes("rejected"))
    return { bg: "bg-amber-950/15 border-amber-500/10", text: "text-amber-400", badge: "DENIED", badgeCls: "bg-amber-950/40 border-amber-500/30 text-amber-400" };
  if (isSys)
    return { bg: "bg-slate-900/40 border-slate-800", text: "text-slate-400", badge: null, badgeCls: "" };
  return { bg: "bg-cyan-950/15 border-cyan-500/5", text: "text-cyan-300", badge: null, badgeCls: "" };
}

export function AgentConversations() {
  const { conversations, demoMode } = useCityStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversations.length]);

  const isWithout = demoMode === "without";

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* Conversations Stream */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 font-mono text-[8.5px]">
        {conversations.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 text-center uppercase tracking-wider text-[8px] gap-1 select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-600 animate-pulse" />
            Awaiting inter-agent telemetry sync...
          </div>
        ) : (
          conversations.map((msg, idx) => {
            const time = new Date(msg.timestamp).toLocaleTimeString("en-IN", { hour12: false });
            const style = getMsgStyle(msg.message, msg.sender, demoMode);

            return (
              <div
                key={idx}
                className={`p-1.5 rounded border flex flex-col gap-1 transition-all duration-300 ${style.bg} ${isWithout ? "opacity-80" : ""}`}
              >
                {/* Header: Sender -> Receiver & Time */}
                <div className="flex items-center justify-between text-[7px] text-slate-500 font-bold border-b border-slate-850 pb-0.5">
                  <div className="flex items-center gap-1">
                    {isWithout ? (
                      <Unlock className="w-2 h-2 text-red-400" />
                    ) : (
                      <Lock className="w-2 h-2 text-emerald-400" />
                    )}
                    <span className="text-cyan-400 font-bold">{msg.sender}</span>
                    {msg.sender !== msg.receiver && (
                      <>
                        <ArrowRight className="w-2 h-2 text-slate-600" />
                        <span className="text-purple-400 font-bold">{msg.receiver}</span>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    {style.badge && (
                      <span className={`px-1 py-0.5 rounded border text-[6px] font-bold ${style.badgeCls}`}>
                        {style.badge}
                      </span>
                    )}
                    <span>{time}</span>
                  </div>
                </div>
                {/* Body Message */}
                <p className={`leading-relaxed text-[8.5px] whitespace-pre-wrap ${style.text}`}>{msg.message}</p>

                {/* ArmorIQ verification footer (only in "with" mode for approved msgs) */}
                {!isWithout && style.badge === "APPROVED" && (
                  <div className="flex items-center gap-1 text-[6.5px] text-emerald-500/70 pt-0.5 border-t border-emerald-500/10">
                    <ShieldCheck className="w-2 h-2" />
                    ArmorIQ Capability Handshake Verified · SHA-256 Sealed
                  </div>
                )}
                {isWithout && (
                  <div className="flex items-center gap-1 text-[6.5px] text-red-500/60 pt-0.5 border-t border-red-500/10">
                    <ShieldAlert className="w-2 h-2" />
                    NO GOVERNANCE · Unverified Channel
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
