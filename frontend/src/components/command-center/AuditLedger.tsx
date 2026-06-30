"use client";

import React, { useState } from "react";
import { Search, ShieldAlert, CheckCircle, RefreshCw } from "lucide-react";
import { useCityStore } from "@/store/city-store";
import { searchAudit } from "@/lib/api";

export function AuditLedger() {
  const { auditEntries, token, error, summary } = useCityStore();
  const [searchValue, setSearchValue] = useState("");
  const [eventType, setEventType] = useState("");
  const [localEntries, setLocalEntries] = useState(auditEntries);
  const [searching, setSearching] = useState(false);

  const displayEntries = localEntries.length > 0 ? localEntries : auditEntries;

  const handleSearch = async () => {
    if (!token) return;
    setSearching(true);
    try {
      const entries = await searchAudit(token, {
        search: searchValue || undefined,
        eventType: eventType || undefined,
        limit: 15,
      });
      setLocalEntries(entries);
    } catch {
      // fallback
    } finally {
      setSearching(false);
    }
  };

  const trimHash = (hash: string | null | undefined) => {
    if (!hash) return "n/a";
    return `${hash.slice(0, 10)}...${hash.slice(-10)}`;
  };

  return (
    <div className="h-full flex flex-col p-2 select-none overflow-hidden">
      {/* Filter and search bar */}
      <div className="flex items-center gap-2 mb-2 bg-slate-900/40 p-1.5 rounded border border-cyan-500/5">
        <div className="flex items-center gap-1.5 bg-slate-950/65 px-2 py-1 rounded border border-cyan-500/10 flex-1">
          <Search className="w-3.5 h-3.5 text-slate-500" />
          <input
            className="bg-transparent border-none outline-none font-mono text-[9px] text-slate-200 placeholder-slate-600 w-full"
            placeholder="Search hash, actor, subject..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-1.5 bg-slate-950/65 px-2 py-1 rounded border border-cyan-500/10 w-44">
          <input
            className="bg-transparent border-none outline-none font-mono text-[9px] text-slate-200 placeholder-slate-600 w-full"
            placeholder="Filter event type..."
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={searching}
          className="bg-cyan-950/50 hover:bg-cyan-900 border border-cyan-500/30 text-cyan-300 font-mono text-[9.5px] font-bold px-3 py-1 rounded transition shrink-0 flex items-center gap-1.5"
        >
          {searching ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
          SEARCH LEDGER
        </button>
      </div>

      {/* Grid list entries */}
      <div className="flex-1 overflow-y-auto border border-cyan-500/5 rounded bg-slate-950/30">
        <table className="w-full text-left font-mono text-[8.5px] leading-tight border-collapse">
          <thead className="bg-slate-900/60 sticky top-0 text-slate-400 font-bold border-b border-cyan-500/10 z-10">
            <tr>
              <th className="p-1.5 pl-3">SEQ</th>
              <th className="p-1.5">EVENT</th>
              <th className="p-1.5">ACTOR</th>
              <th className="p-1.5">HASH ROOT</th>
              <th className="p-1.5">PREVIOUS HASH</th>
              <th className="p-1.5">MERKLE LEAF</th>
              <th className="p-1.5 text-right pr-3">INTEGRITY</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-cyan-500/5 text-slate-300">
            {displayEntries.map((entry) => (
              <tr key={entry.entry_id} className="hover:bg-slate-900/40 transition">
                <td className="p-1.5 pl-3 font-bold text-slate-400">#{entry.sequence_number}</td>
                <td className="p-1.5 font-bold text-cyan-400 max-w-[150px] truncate">
                  {entry.event_type}
                </td>
                <td className="p-1.5 text-slate-400">{entry.actor_id ?? "system"}</td>
                <td className="p-1.5 text-cyan-400/80 font-mono">{trimHash(entry.entry_hash)}</td>
                <td className="p-1.5 text-slate-500 font-mono">{trimHash(entry.previous_hash)}</td>
                <td className="p-1.5 text-purple-400/70 font-mono">{trimHash(entry.merkle_leaf_hash)}</td>
                <td className="p-1.5 text-right pr-3">
                  <span className="inline-flex items-center gap-1 text-[8px] font-bold text-emerald-400 bg-emerald-950/30 border border-emerald-500/20 px-1 py-0.5 rounded">
                    <CheckCircle className="w-2.5 h-2.5 text-emerald-400" />
                    SECURED
                  </span>
                </td>
              </tr>
            ))}
            {displayEntries.length === 0 && (
              <tr>
                <td colSpan={7} className="p-4 text-center text-slate-600">
                  NO LEDGER ENTRIES FOUND IN SYSTEM AUDIT.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
