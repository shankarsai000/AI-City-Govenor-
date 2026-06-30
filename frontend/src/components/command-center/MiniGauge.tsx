"use client";

import React from "react";

interface MiniGaugeProps {
  value: number; // 0 to 100
  size?: number;
  strokeWidth?: number;
  title: string;
  color?: string;
  statusText?: string;
}

export function MiniGauge({
  value,
  size = 54,
  strokeWidth = 4.5,
  title,
  color = "rgb(34, 211, 238)", // default cyan
  statusText,
}: MiniGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const clampedValue = Math.min(Math.max(value, 0), 100);
  const strokeDashoffset = circumference - (clampedValue / 100) * circumference;

  return (
    <div className="flex items-center gap-3 select-none">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Background track circle */}
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            className="stroke-slate-800"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {/* Animated active progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)" }}
          />
        </svg>
        {/* Centered value reading */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono text-[10px] font-bold" style={{ color }}>
            {Math.round(clampedValue)}%
          </span>
        </div>
      </div>

      <div className="flex flex-col font-mono">
        <span className="text-[10px] tracking-wide text-slate-500 font-bold uppercase">{title}</span>
        <span className="text-[11px] font-bold text-slate-300 tracking-wider">
          {statusText ?? `${Math.round(clampedValue)}%`}
        </span>
      </div>
    </div>
  );
}
