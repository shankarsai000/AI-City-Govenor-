"use client";

import React, { useEffect, useRef } from "react";
import { useCityStore } from "@/store/city-store";

export function ThreatRadar() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { cityState } = useCityStore();

  useEffect(() => {
    let animationFrameId: number;

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const size = canvas.width;
      const center = size / 2;
      const radius = size / 2 - 8;

      ctx.clearRect(0, 0, size, size);

      // 1. Draw outer circle radar framework
      ctx.strokeStyle = "rgba(34, 211, 238, 0.15)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(center, center, radius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.strokeStyle = "rgba(34, 211, 238, 0.05)";
      ctx.beginPath();
      ctx.arc(center, center, radius * 0.65, 0, Math.PI * 2);
      ctx.arc(center, center, radius * 0.35, 0, Math.PI * 2);
      ctx.stroke();

      // Crosshairs axes lines
      ctx.beginPath();
      ctx.moveTo(center, 4);
      ctx.lineTo(center, size - 4);
      ctx.moveTo(4, center);
      ctx.lineTo(size - 4, center);
      ctx.stroke();

      // 2. Draw rotating radar scan line
      const angle = (Date.now() / 1200) % (Math.PI * 2);
      const gradient = ctx.createRadialGradient(center, center, 0, center, center, radius);
      gradient.addColorStop(0, "rgba(34, 211, 238, 0.0)");
      gradient.addColorStop(1, "rgba(34, 211, 238, 0.15)");

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.arc(center, center, radius, angle - 0.25, angle);
      ctx.lineTo(center, center);
      ctx.fill();

      // Render outer scanning sweeps line
      ctx.strokeStyle = "rgba(34, 211, 238, 0.4)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.lineTo(center + Math.cos(angle) * radius, center + Math.sin(angle) * radius);
      ctx.stroke();

      // 3. Render active threats/incidents
      if (cityState) {
        cityState.emergency.active_incidents.forEach((inc, idx) => {
          // Calculate arbitrary threat dot angle from incident ID/index
          const theta = (idx * 1.5 + 0.8) % (Math.PI * 2);
          const distance = radius * (0.4 + (idx * 0.15) % 0.5);

          const dotX = center + Math.cos(theta) * distance;
          const dotY = center + Math.sin(theta) * distance;

          // Flashing warning red dot
          const alpha = 0.5 + Math.sin(Date.now() / 150) * 0.4;
          ctx.fillStyle = `rgba(255, 51, 102, ${alpha})`;
          ctx.beginPath();
          ctx.arc(dotX, dotY, 4, 0, Math.PI * 2);
          ctx.fill();

          // Outlines
          ctx.strokeStyle = "rgba(255, 51, 102, 0.6)";
          ctx.beginPath();
          ctx.arc(dotX, dotY, 9, 0, Math.PI * 2);
          ctx.stroke();

          // Text marker ID
          ctx.fillStyle = "rgba(255, 51, 102, 0.8)";
          ctx.font = "bold 6.5px monospace";
          ctx.fillText("ALRT", dotX + 7, dotY + 2);
        });
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationFrameId);
  }, [cityState]);

  return (
    <div className="flex flex-col items-center select-none font-mono">
      <canvas ref={canvasRef} width={96} height={96} className="bg-slate-950/20 rounded-full" />
      <span className="text-[7.5px] font-bold text-slate-500 uppercase tracking-widest mt-1.5 animate-pulse-glow">
        threat grid radar
      </span>
    </div>
  );
}
