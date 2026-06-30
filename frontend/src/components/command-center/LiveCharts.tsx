"use client";

import React from "react";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { useCityStore } from "@/store/city-store";

export function LiveCharts() {
  const { history } = useCityStore();

  // Map history arrays to Recharts friendly format
  const chartData = history.timestamps.map((time, idx) => {
    return {
      time: new Date(time).toLocaleTimeString("en-IN", { hour12: false, second: "2-digit", minute: "2-digit" }),
      traffic: history.traffic[idx] ?? 0,
      power: history.power[idx] ?? 0,
      water: history.water[idx] ?? 0,
      emergency: history.emergency[idx] ?? 0,
    };
  });

  const renderAreaChart = (
    dataKey: "traffic" | "power" | "water" | "emergency",
    title: string,
    color: string,
    fillId: string
  ) => {
    return (
      <div className="flex-1 h-full flex flex-col p-2 bg-slate-950/40 border-r border-cyan-500/5 last:border-r-0 select-none">
        <span className="font-mono text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">
          {title}
        </span>
        <div className="flex-1 w-full min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 2, right: 2, left: -25, bottom: 2 }}>
              <defs>
                <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="time"
                tick={{ fill: "#64748b", fontSize: 7, fontFamily: "monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "#64748b", fontSize: 7, fontFamily: "monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(15, 23, 42, 0.9)",
                  border: "1px solid rgba(34, 211, 238, 0.2)",
                  fontSize: "8px",
                  fontFamily: "monospace",
                  color: "#e2e8f0",
                }}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={1.5}
                fillOpacity={1}
                fill={`url(#${fillId})`}
                animationDuration={300}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex items-center justify-between">
      {renderAreaChart("traffic", "Traffic Congestion Trend", "#22d3ee", "trafficGlow")}
      {renderAreaChart("power", "Power Grid Load Peak", "#a855f7", "powerGlow")}
      {renderAreaChart("water", "Hydraulic Pressure (PSI)", "#3b82f6", "waterGlow")}
      {renderAreaChart("emergency", "Civil Distress Factor", "#f59e0b", "emergencyGlow")}
    </div>
  );
}
