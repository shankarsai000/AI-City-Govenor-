"use client";

import React, { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2, CloudRain, Zap, Droplet, Layers } from "lucide-react";
import { useCityStore } from "@/store/city-store";

interface Vehicle {
  roadIndex: number;
  progress: number;
  speed: number;
  color: string;
  isEmergency: boolean;
}

interface RainDrop {
  x: number;
  y: number;
  length: number;
  speed: number;
}

// ── Fixed Infrastructure Nodes ──────────────────────────────────────
const roads = [
  { start: { x: 100, y: 50 }, end: { x: 100, y: 550 } },
  { start: { x: 300, y: 50 }, end: { x: 300, y: 550 } },
  { start: { x: 500, y: 50 }, end: { x: 500, y: 550 } },
  { start: { x: 55, y: 150 }, end: { x: 545, y: 150 } },
  { start: { x: 55, y: 350 }, end: { x: 545, y: 350 } },
  { start: { x: 55, y: 480 }, end: { x: 545, y: 480 } },
];

const buildings = [
  { x: 130, y: 70, w: 40, h: 60, type: "residential", label: "Sector 1 Res" },
  { x: 190, y: 70, w: 60, h: 50, type: "commercial", label: "Tech Hub" },
  { x: 330, y: 70, w: 70, h: 60, type: "hospital", label: "Central Medical" },
  { x: 420, y: 80, w: 50, h: 50, type: "power", label: "Substation S1" },
  { x: 130, y: 220, w: 50, h: 80, type: "industrial", label: "Production C" },
  { x: 210, y: 220, w: 40, h: 40, type: "residential", label: "Sector 2" },
  { x: 330, y: 220, w: 60, h: 60, type: "water", label: "Aqua Purify" },
  { x: 420, y: 220, w: 50, h: 60, type: "emergency", label: "Emergency HQ" },
  { x: 130, y: 380, w: 100, h: 80, type: "commercial", label: "Downtown Plaza" },
  { x: 330, y: 380, w: 80, h: 70, type: "residential", label: "S3 Towers" },
];

const intersections = [
  { id: "I-1", x: 100, y: 150 },
  { id: "I-2", x: 300, y: 150 },
  { id: "I-3", x: 500, y: 150 },
  { id: "I-4", x: 100, y: 350 },
  { id: "I-5", x: 300, y: 350 },
  { id: "I-6", x: 500, y: 350 },
];

// Transmission Line vectors (Power AI grid mapping)
const powerLines = [
  { start: { x: 445, y: 105 }, end: { x: 365, y: 100 } }, // Substation S1 -> Medical
  { start: { x: 445, y: 105 }, end: { x: 220, y: 95 } },  // Substation S1 -> Tech Hub
  { start: { x: 445, y: 130 }, end: { x: 445, y: 220 } }, // Substation S1 -> Emergency HQ
  { start: { x: 445, y: 130 }, end: { x: 370, y: 380 } }, // Substation S1 -> S3 Towers
];

// Pipeline vectors (Water AI grid mapping)
const pipelines = [
  { start: { x: 360, y: 250 }, end: { x: 230, y: 240 } }, // Purify -> Sector 2
  { start: { x: 360, y: 250 }, end: { x: 155, y: 260 } }, // Purify -> Production C
  { start: { x: 360, y: 250 }, end: { x: 180, y: 420 } }, // Purify -> Downtown Plaza
];

// Diagonal Metro Line path
const metroPath = { start: { x: 60, y: 520 }, end: { x: 540, y: 80 } };

export function DigitalTwinCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { cityState, simulatorRunning } = useCityStore();

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activeLayer, setActiveLayer] = useState<"hybrid" | "energy" | "hydro" | "weather">("hybrid");

  // Persistent Animation States
  const vehiclesRef = useRef<Vehicle[]>([]);
  const rainDropsRef = useRef<RainDrop[]>([]);
  const metroProgressRef = useRef(0);
  const powerPulseRef = useRef(0);
  const waterPulseRef = useRef(0);
  const lightningFlashRef = useRef(0);

  // Initialize persistent vectors
  useEffect(() => {
    // Vehicles
    const vList: Vehicle[] = [];
    for (let i = 0; i < 22; i++) {
      vList.push({
        roadIndex: Math.floor(Math.random() * roads.length),
        progress: Math.random(),
        speed: 0.001 + Math.random() * 0.0014,
        color: i % 5 === 0 ? "#a855f7" : "#22d3ee",
        isEmergency: false,
      });
    }
    vehiclesRef.current = vList;

    // Weather Raindrops
    const rList: RainDrop[] = [];
    for (let i = 0; i < 60; i++) {
      rList.push({
        x: Math.random() * 600,
        y: Math.random() * 600,
        length: 5 + Math.random() * 8,
        speed: 4 + Math.random() * 4,
      });
    }
    rainDropsRef.current = rList;
  }, []);

  // Update en-route ambulances based on incidents
  useEffect(() => {
    if (!cityState) return;
    const count = cityState.emergency.active_incidents.length;
    const current = vehiclesRef.current;
    const emergencyOnly = current.filter((v) => v.isEmergency);

    if (count > emergencyOnly.length) {
      current.push({
        roadIndex: Math.floor(Math.random() * roads.length),
        progress: 0,
        speed: 0.0035, // Faster
        color: "#ff3366",
        isEmergency: true,
      });
    } else if (count === 0) {
      vehiclesRef.current = current.filter((v) => !v.isEmergency);
    }
  }, [cityState?.emergency.active_incidents.length]);

  // Fullscreen Handlers
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true));
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false));
    }
  };

  useEffect(() => {
    const handleFs = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handleFs);
    return () => document.removeEventListener("fullscreenchange", handleFs);
  }, []);

  // Canvas Resize observer
  useEffect(() => {
    const c = canvasRef.current;
    const p = containerRef.current;
    if (!c || !p) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        c.width = entry.contentRect.width;
        c.height = entry.contentRect.height;
      }
    });

    resizeObserver.observe(p);
    return () => resizeObserver.disconnect();
  }, []);

  // 60 FPS Render loop
  useEffect(() => {
    let raf: number;

    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const W = canvas.width;
      const H = canvas.height;

      ctx.clearRect(0, 0, W, H);

      // Proportion scaling to fit 600x600 layout
      const scale = Math.min(W / 600, H / 600);
      const offX = (W - 600 * scale) / 2;
      const offY = (H - 600 * scale) / 2;

      ctx.save();
      ctx.translate(offX, offY);
      ctx.scale(scale, scale);

      // 1. Draw Grid Network
      ctx.strokeStyle = "rgba(34, 211, 238, 0.02)";
      ctx.lineWidth = 1;
      for (let x = 0; x <= 600; x += 40) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 600); ctx.stroke();
      }
      for (let y = 0; y <= 600; y += 40) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(600, y); ctx.stroke();
      }

      // 2. Draw Subterranean Metro Track (Hybrid and Hybrid-alike layers)
      if (activeLayer === "hybrid" || activeLayer === "weather") {
        ctx.strokeStyle = "rgba(30, 41, 59, 0.5)";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(metroPath.start.x, metroPath.start.y);
        ctx.lineTo(metroPath.end.x, metroPath.end.y);
        ctx.stroke();

        ctx.strokeStyle = "rgba(34, 211, 238, 0.18)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 5]);
        ctx.beginPath();
        ctx.moveTo(metroPath.start.x, metroPath.start.y);
        ctx.lineTo(metroPath.end.x, metroPath.end.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Animate Metro train progress loop
        metroProgressRef.current += 0.0025;
        if (metroProgressRef.current >= 1) metroProgressRef.current = 0;

        const mx = metroPath.start.x + (metroPath.end.x - metroPath.start.x) * metroProgressRef.current;
        const my = metroPath.start.y + (metroPath.end.y - metroPath.start.y) * metroProgressRef.current;

        // Metro train capsule
        ctx.fillStyle = "#e2e8f0";
        ctx.shadowColor = "#22d3ee";
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.arc(mx, my, 4.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0; // reset
      }

      // 3. Draw Road system (Hybrid / Weather layers)
      if (activeLayer === "hybrid" || activeLayer === "weather") {
        ctx.strokeStyle = "rgba(148, 163, 184, 0.12)";
        ctx.lineWidth = 12;
        roads.forEach((r) => {
          ctx.beginPath(); ctx.moveTo(r.start.x, r.start.y); ctx.lineTo(r.end.x, r.end.y); ctx.stroke();
        });

        // Center dashes
        ctx.strokeStyle = "rgba(226, 232, 240, 0.15)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 6]);
        roads.forEach((r) => {
          ctx.beginPath(); ctx.moveTo(r.start.x, r.start.y); ctx.lineTo(r.end.x, r.end.y); ctx.stroke();
        });
        ctx.setLineDash([]);
      }

      // 4. Draw Power Transmission Lines (Energy / Hybrid layers)
      if (activeLayer === "hybrid" || activeLayer === "energy") {
        ctx.strokeStyle = "rgba(168, 85, 247, 0.25)";
        ctx.lineWidth = 1.5;
        powerLines.forEach((line) => {
          ctx.beginPath();
          ctx.moveTo(line.start.x, line.start.y);
          ctx.lineTo(line.end.x, line.end.y);
          ctx.stroke();
        });

        // Animate grid load transmission pulses
        powerPulseRef.current += 0.005;
        if (powerPulseRef.current >= 1) powerPulseRef.current = 0;

        ctx.fillStyle = "#a855f7";
        ctx.shadowColor = "#a855f7";
        ctx.shadowBlur = 4;
        powerLines.forEach((line) => {
          const px = line.start.x + (line.end.x - line.start.x) * powerPulseRef.current;
          const py = line.start.y + (line.end.y - line.start.y) * powerPulseRef.current;
          ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();
        });
        ctx.shadowBlur = 0;
      }

      // 5. Draw Water Pipelines (Hydro / Hybrid layers)
      if (activeLayer === "hybrid" || activeLayer === "hydro") {
        ctx.strokeStyle = "rgba(59, 130, 246, 0.3)";
        ctx.lineWidth = 2;
        pipelines.forEach((pipe) => {
          ctx.beginPath();
          ctx.moveTo(pipe.start.x, pipe.start.y);
          ctx.lineTo(pipe.end.x, pipe.end.y);
          ctx.stroke();
        });

        // Animate water flow pulses
        waterPulseRef.current += 0.004;
        if (waterPulseRef.current >= 1) waterPulseRef.current = 0;

        ctx.fillStyle = "#3b82f6";
        ctx.shadowColor = "#60a5fa";
        ctx.shadowBlur = 4;
        pipelines.forEach((pipe) => {
          const wx = pipe.start.x + (pipe.end.x - pipe.start.x) * waterPulseRef.current;
          const wy = pipe.start.y + (pipe.end.y - pipe.start.y) * waterPulseRef.current;
          ctx.beginPath(); ctx.arc(wx, wy, 2.5, 0, Math.PI * 2); ctx.fill();
        });
        ctx.shadowBlur = 0;
      }

      // 6. Draw Buildings
      buildings.forEach((b) => {
        let fill = "rgba(30, 41, 59, 0.45)";
        let border = "rgba(34, 211, 238, 0.15)";
        ctx.lineWidth = 1;

        // Custom styling for layers
        if (activeLayer === "energy" && b.type === "power") {
          fill = "rgba(168, 85, 247, 0.15)";
          border = "rgba(168, 85, 247, 0.6)";
        } else if (activeLayer === "hydro" && b.type === "water") {
          fill = "rgba(59, 130, 246, 0.15)";
          border = "rgba(59, 130, 246, 0.6)";
        } else if (b.type === "hospital") {
          border = "rgba(16, 185, 129, 0.4)";
        }

        // Apply crisis colors
        if (cityState && cityState.power.blackout_zones.length > 0 && b.type === "power") {
          fill = "rgba(239, 68, 68, 0.15)";
          border = "rgba(239, 68, 68, 0.6)";
        }

        ctx.fillStyle = fill;
        ctx.strokeStyle = border;
        ctx.beginPath();
        ctx.roundRect(b.x, b.y, b.w, b.h, 3);
        ctx.fill();
        ctx.stroke();

        // Building text label
        ctx.fillStyle = "rgba(148, 163, 184, 0.7)";
        ctx.font = "7px monospace";
        ctx.fillText(b.label, b.x + 3, b.y + b.h - 5);
      });

      // 7. Draw Intersections and Traffic signals
      if (activeLayer === "hybrid" || activeLayer === "weather") {
        intersections.forEach((int) => {
          ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
          ctx.strokeStyle = "rgba(34, 211, 238, 0.25)";
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(int.x, int.y, 7, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

          let sigCol = "rgba(0, 255, 136, 0.8)";
          if (cityState) {
            const phase = cityState.traffic.intersections[int.id]?.signal_phase;
            if (phase === "red" || phase === "emergency_red") sigCol = "rgba(255, 51, 102, 0.8)";
            else if (phase === "yellow") sigCol = "rgba(255, 170, 0, 0.8)";
          }
          ctx.fillStyle = sigCol;
          ctx.beginPath(); ctx.arc(int.x, int.y, 2.8, 0, Math.PI * 2); ctx.fill();
        });
      }

      // 8. Draw Vehicles
      if (activeLayer === "hybrid" || activeLayer === "weather") {
        vehiclesRef.current.forEach((v) => {
          const road = roads[v.roadIndex];
          if (!road) return;
          v.progress += v.speed;
          if (v.progress >= 1) {
            v.progress = 0;
            v.roadIndex = Math.floor(Math.random() * roads.length);
          }
          const vx = road.start.x + (road.end.x - road.start.x) * v.progress;
          const vy = road.start.y + (road.end.y - road.start.y) * v.progress;

          if (v.isEmergency) {
            const blink = Math.floor(Date.now() / 150) % 2 === 0;
            ctx.fillStyle = blink ? "#ff3366" : "#3b82f6";
            ctx.beginPath(); ctx.arc(vx, vy, 4, 0, Math.PI * 2); ctx.fill();
          } else {
            ctx.fillStyle = v.color;
            ctx.beginPath(); ctx.arc(vx, vy, 2.5, 0, Math.PI * 2); ctx.fill();
          }
        });
      }

      // 9. Draw Incident markers (Crimson pulsing alerts)
      if (cityState) {
        cityState.emergency.active_incidents.forEach((inc, i) => {
          const alpha = 0.4 + Math.sin(Date.now() / 150) * 0.35;
          const ix = 160 + i * 120;
          const iy = 250;

          ctx.fillStyle = `rgba(255, 51, 102, ${alpha})`;
          ctx.strokeStyle = "rgba(255, 51, 102, 0.6)";
          ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(ix, iy, 12, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

          ctx.fillStyle = "#ff3366";
          ctx.font = "bold 8.5px monospace";
          ctx.fillText("!", ix - 2, iy + 3);
        });
      }

      // 10. Draw Weather Overlays (Weather layer or general crisis storm active)
      const isStormActive = cityState?.emergency.declared_emergencies.some((d) => d.includes("STORM")) || false;
      const isFloodActive = cityState?.emergency.active_incidents.some((i) => i.location.includes("Sector 4")) || false;

      if (activeLayer === "weather" || isStormActive || isFloodActive) {
        // Darken environment for weather storm
        ctx.fillStyle = "rgba(2, 6, 23, 0.35)";
        ctx.fillRect(0, 0, 600, 600);

        // Draw and update falling raindrops
        ctx.strokeStyle = "rgba(186, 230, 253, 0.4)";
        ctx.lineWidth = 1;
        rainDropsRef.current.forEach((drop) => {
          ctx.beginPath();
          ctx.moveTo(drop.x, drop.y);
          ctx.lineTo(drop.x + 1.5, drop.y + drop.length);
          ctx.stroke();

          // Drop movement
          drop.y += drop.speed;
          drop.x += 0.3; // wind angle drift
          if (drop.y > 600) {
            drop.y = -drop.length;
            drop.x = Math.random() * 600;
          }
        });

        // Lightning flash triggers during heavy storm
        if (isStormActive && Math.random() > 0.98) {
          lightningFlashRef.current = 8;
        }

        if (lightningFlashRef.current > 0) {
          lightningFlashRef.current--;
          ctx.fillStyle = `rgba(224, 242, 254, ${0.15 * lightningFlashRef.current})`;
          ctx.fillRect(0, 0, 600, 600);
        }
      }

      ctx.restore();
      raf = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(raf);
  }, [cityState, activeLayer]);

  return (
    <div ref={containerRef} className="h-full w-full relative bg-[#01030a]">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />

      {/* Layer selector top-left */}
      <div className="absolute top-2 left-2 flex items-center gap-1.5 z-10 bg-slate-950/60 border border-cyan-500/10 p-1 rounded backdrop-blur">
        <Layers className="w-3.5 h-3.5 text-cyan-400 ml-1 shrink-0" />
        <button
          onClick={() => setActiveLayer("hybrid")}
          className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold transition ${
            activeLayer === "hybrid" ? "bg-cyan-950 text-cyan-300 border border-cyan-400/30" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          HYBRID
        </button>
        <button
          onClick={() => setActiveLayer("energy")}
          className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold transition ${
            activeLayer === "energy" ? "bg-purple-950 text-purple-300 border border-purple-400/30" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          ENERGY
        </button>
        <button
          onClick={() => setActiveLayer("hydro")}
          className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold transition ${
            activeLayer === "hydro" ? "bg-blue-950 text-blue-300 border border-blue-400/30" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          HYDRO
        </button>
        <button
          onClick={() => setActiveLayer("weather")}
          className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold transition ${
            activeLayer === "weather" ? "bg-sky-950 text-sky-300 border border-sky-400/30" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          WEATHER
        </button>
      </div>

      {/* Fullscreen toggle top-right */}
      <button
        onClick={toggleFullscreen}
        className="absolute top-2 right-2 z-10 p-1.5 bg-slate-900/70 hover:bg-slate-800 border border-cyan-500/10 text-cyan-400 rounded transition"
      >
        {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
      </button>

      {/* Footer metadata */}
      <div className="absolute bottom-2 left-2 bg-slate-950/70 border border-cyan-500/10 px-2.5 py-1 rounded font-mono text-[8px] text-slate-500 z-10 flex gap-3 backdrop-blur">
        <span>TWIN v3.0</span>
        <span>60 Hz</span>
        <span className="uppercase">{activeLayer} LAYER</span>
      </div>
    </div>
  );
}
