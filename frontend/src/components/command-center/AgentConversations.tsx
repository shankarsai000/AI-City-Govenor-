"use client";

import React, { useEffect, useRef } from "react";
import { MessageSquare, ArrowRight } from "lucide-react";
import { useCityStore } from "@/store/city-store";

export function AgentConversations() {
  const { conversations } = useCityStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversations.length]);

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
            
            // Format sender/receiver tags
            const isSys = msg.sender === "System Console";
            const bubbleStyle = isSys
              ? "bg-slate-900/40 border-slate-800 text-slate-400"
              : "bg-cyan-950/20 border-cyan-500/5 text-cyan-300";

            return (
              <div
                key={idx}
                className={`p-1.5 rounded border flex flex-col gap-1 transition-all ${bubbleStyle}`}
              >
                {/* Header: Sender -> Receiver & Time */}
                <div className="flex items-center justify-between text-[7px] text-slate-500 font-bold border-b border-slate-850 pb-0.5">
                  <div className="flex items-center gap-1">
                    <span className="text-cyan-400 font-bold">{msg.sender}</span>
                    {msg.sender !== msg.receiver && (
                      <>
                        <ArrowRight className="w-2 h-2 text-slate-600" />
                        <span className="text-purple-400 font-bold">{msg.receiver}</span>
                      </>
                    )}
                  </div>
                  <span>{time}</span>
                </div>
                {/* Body Message */}
                <p className="leading-relaxed text-[8.5px] whitespace-pre-wrap">{msg.message}</p>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
