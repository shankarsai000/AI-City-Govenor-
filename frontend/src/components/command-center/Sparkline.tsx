"use client";

import React from "react";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fillColor?: string;
}

export function Sparkline({
  data,
  width = 110,
  height = 24,
  color = "#22d3ee",
  fillColor = "rgba(34, 211, 238, 0.05)",
}: SparklineProps) {
  if (!data || data.length === 0) return null;

  const points = data.length > 1 ? data : [data[0] || 0, data[0] || 0];

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min === 0 ? 1 : max - min;

  const widthStep = width / (points.length - 1);
  const pointsStr = points
    .map((val, index) => {
      const x = index * widthStep;
      // Invert y because SVG y goes down
      const y = height - ((val - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  // Create area path
  const fillPath = `0,${height} ${pointsStr} ${width},${height}`;

  return (
    <svg width={width} height={height} className="overflow-visible select-none">
      {/* Area under the line */}
      <polygon points={fillPath} fill={fillColor} />
      {/* Sparkline path */}
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={pointsStr}
      />
      {/* Pulse circle on the latest coordinate */}
      {points.length > 0 && (
        <circle
          cx={width}
          cy={height - (((points[points.length - 1] ?? 0) - min) / range) * (height - 4) - 2}
          r="1.8"
          fill={color}
          className="animate-pulse"
        />
      )}
    </svg>
  );
}
