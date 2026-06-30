"use client";

/* ═══════════════════════════════════════════════════════════════════
   AI CITY GOVERNOR — ZUSTAND STORE
   Central state management for the Command Center.
   Handles auto-login, polling, WebSocket, and simulator integration.
   ═══════════════════════════════════════════════════════════════════ */

import { create } from "zustand";
import {
  autoLogin,
  buildWebSocketUrl,
  CityState,
  DashboardSummary,
  AgentRecord,
  ActionRecord,
  ApprovalRecord,
  AuditRecord,
  LiveEventEnvelope,
  LockRecord,
  getDashboardSnapshot,
  SessionInfo,
  DecisionGraphRecord,
  getDecisionGraphs,
} from "@/lib/api";

// ── Telemetry Metrics ──────────────────────────────────────────────
interface TelemetryMetrics {
  fps: number;
  latency: number;
  eventsPerSec: number;
  uptime: number;
}

// ── History Ring Buffer ────────────────────────────────────────────
export interface DomainHistory {
  traffic: number[];
  power: number[];
  water: number[];
  emergency: number[];
  timestamps: string[];
}

// ── Store Shape ────────────────────────────────────────────────────
interface CityStore {
  // Auth
  token: string | null;
  session: SessionInfo | null;
  isAuthenticated: boolean;

  // Core data
  summary: DashboardSummary | null;
  cityState: CityState | null;
  agents: AgentRecord[];
  actions: ActionRecord[];
  approvals: ApprovalRecord[];
  auditEntries: AuditRecord[];
  locks: LockRecord[];
  decisionGraphs: DecisionGraphRecord[];

  // Real-time
  liveEvents: LiveEventEnvelope[];
  wsConnected: boolean;
  conversations: Array<{ sender: string; receiver: string; message: string; timestamp: string }>;

  // Telemetry
  telemetry: TelemetryMetrics;
  history: DomainHistory;

  // Replay timeline state
  replayBuffer: Array<{
    timestamp: string;
    cityState: CityState;
    summary: DashboardSummary;
    liveEvents: LiveEventEnvelope[];
    conversations: Array<{ sender: string; receiver: string; message: string; timestamp: string }>;
  }>;
  isReplayActive: boolean;
  replayIndex: number;

  // UI state
  loading: boolean;
  error: string | null;
  activeBottomTab: "charts" | "audit" | "simulation" | "threat";
  simulatorRunning: boolean;

  // Actions
  initialize: () => Promise<void>;
  refreshData: () => Promise<void>;
  addLiveEvent: (event: LiveEventEnvelope) => void;
  addConversation: (sender: string, receiver: string, message: string) => void;
  setWsConnected: (connected: boolean) => void;
  setActiveBottomTab: (tab: "charts" | "audit" | "simulation" | "threat") => void;
  updateTelemetry: (partial: Partial<TelemetryMetrics>) => void;
  setSimulatorRunning: (running: boolean) => void;
  setReplayMode: (active: boolean) => void;
  scrubTimeline: (index: number) => void;
  cleanup: () => void;
}

const MAX_EVENTS = 50;
const MAX_HISTORY = 60;

export const useCityStore = create<CityStore>((set, get) => {
  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let eventsSocket: WebSocket | null = null;
  let approvalsSocket: WebSocket | null = null;
  let eventCounter = 0;
  let eventRateInterval: ReturnType<typeof setInterval> | null = null;
  let liveStateBackup: any = null;

  function startWebSockets(token: string) {
    try {
      eventsSocket = new WebSocket(buildWebSocketUrl("/ws/events", token));
      approvalsSocket = new WebSocket(buildWebSocketUrl("/ws/approvals", token));

      const onOpen = () => set({ wsConnected: true });
      const onClose = () => set({ wsConnected: false });
      const onMessage = (event: MessageEvent<string>) => {
        try {
          const payload = JSON.parse(event.data) as LiveEventEnvelope;
          get().addLiveEvent(payload);
          eventCounter++;
        } catch {
          // ignore malformed
        }
      };

      eventsSocket.addEventListener("open", onOpen);
      eventsSocket.addEventListener("close", onClose);
      eventsSocket.addEventListener("message", onMessage);
      approvalsSocket.addEventListener("open", onOpen);
      approvalsSocket.addEventListener("close", onClose);
      approvalsSocket.addEventListener("message", onMessage);
    } catch {
      // WebSocket connection failed — will show as disconnected
    }
  }

  function startPolling(token: string) {
    pollInterval = setInterval(() => {
      void get().refreshData();
    }, 5000);

    // Event rate tracker
    eventRateInterval = setInterval(() => {
      set((s) => ({
        telemetry: { ...s.telemetry, eventsPerSec: eventCounter },
      }));
      eventCounter = 0;
    }, 1000);

    // Initial fetch of decision graphs
    void getDecisionGraphs(token, 10).then((graphs) => {
      set({ decisionGraphs: graphs });
    }).catch(() => { /* ignore */ });
  }

  return {
    // Initial state
    token: null,
    session: null,
    isAuthenticated: false,
    summary: null,
    cityState: null,
    agents: [],
    actions: [],
    approvals: [],
    auditEntries: [],
    locks: [],
    decisionGraphs: [],
    liveEvents: [],
    wsConnected: false,
    conversations: [],
    replayBuffer: [],
    isReplayActive: false,
    replayIndex: 0,
    telemetry: { fps: 60, latency: 0, eventsPerSec: 0, uptime: 0 },
    history: { traffic: [], power: [], water: [], emergency: [], timestamps: [] },
    loading: true,
    error: null,
    activeBottomTab: "charts",
    simulatorRunning: false,

    initialize: async () => {
      set({ loading: true, error: null });
      const result = await autoLogin();
      if ("error" in result) {
        set({ loading: false, error: result.error });
        return;
      }

      set({
        token: result.token,
        session: result.session,
        isAuthenticated: true,
      });

      // Fetch initial data
      await get().refreshData();
      set({ loading: false });

      // Start real-time systems
      startWebSockets(result.token);
      startPolling(result.token);
    },

    refreshData: async () => {
      const { token, isReplayActive, replayBuffer, liveEvents, conversations } = get();
      if (!token) return;

      const startTime = performance.now();
      try {
        const snapshot = await getDashboardSnapshot(token);
        const latency = Math.round(performance.now() - startTime);

        // Capture new frame for timeline replay
        const newFrame = {
          timestamp: new Date().toISOString(),
          cityState: snapshot.cityState,
          summary: snapshot.summary,
          liveEvents: [...liveEvents],
          conversations: [...conversations],
        };

        const updatedBuffer = [...replayBuffer, newFrame].slice(-60);

        set((state) => {
          // Append to history ring buffer
          const newHistory = { ...state.history };
          const congestion = snapshot.cityState.traffic.congestion_level * 100;
          const gridLoad = (snapshot.cityState.power.grid_load_mw / Math.max(snapshot.cityState.power.capacity_mw, 1)) * 100;
          const waterPressure = Math.min(snapshot.cityState.water.pressure_psi, 100);
          const emergencyScore = snapshot.cityState.emergency.alert_level === "green" ? 10 :
            snapshot.cityState.emergency.alert_level === "yellow" ? 50 : 90;

          newHistory.traffic = [...newHistory.traffic.slice(-(MAX_HISTORY - 1)), congestion];
          newHistory.power = [...newHistory.power.slice(-(MAX_HISTORY - 1)), gridLoad];
          newHistory.water = [...newHistory.water.slice(-(MAX_HISTORY - 1)), waterPressure];
          newHistory.emergency = [...newHistory.emergency.slice(-(MAX_HISTORY - 1)), emergencyScore];
          newHistory.timestamps = [...newHistory.timestamps.slice(-(MAX_HISTORY - 1)), new Date().toISOString()];

          if (state.isReplayActive) {
            // Keep collecting new data in the background, but do not touch active display states
            return {
              replayBuffer: updatedBuffer,
              error: null,
              telemetry: { ...state.telemetry, latency },
              history: newHistory,
            };
          }

          return {
            summary: snapshot.summary,
            cityState: snapshot.cityState,
            agents: snapshot.agents,
            actions: snapshot.actions,
            approvals: snapshot.approvals,
            auditEntries: snapshot.auditEntries,
            locks: snapshot.locks,
            replayBuffer: updatedBuffer,
            error: null,
            telemetry: { ...state.telemetry, latency },
            history: newHistory,
          };
        });
      } catch (err) {
        set({ error: err instanceof Error ? err.message : "Failed to refresh" });
      }
    },

    addLiveEvent: (event) => {
      set((state) => ({
        liveEvents: [event, ...state.liveEvents].slice(0, MAX_EVENTS),
      }));
    },

    addConversation: (sender, receiver, message) => {
      set((state) => ({
        conversations: [...state.conversations, { sender, receiver, message, timestamp: new Date().toISOString() }].slice(-30),
      }));
    },

    setWsConnected: (connected) => set({ wsConnected: connected }),

    setActiveBottomTab: (tab) => set({ activeBottomTab: tab }),

    updateTelemetry: (partial) =>
      set((state) => ({
        telemetry: { ...state.telemetry, ...partial },
      })),

    setSimulatorRunning: (running) => set({ simulatorRunning: running }),

    setReplayMode: (active) => {
      if (active) {
        const { cityState, summary, liveEvents, conversations } = get();
        if (cityState && summary) {
          liveStateBackup = { cityState, summary, liveEvents, conversations };
        }
        const buffer = get().replayBuffer;
        if (buffer.length > 0) {
          const idx = buffer.length - 1;
          const frame = buffer[idx];
          if (frame) {
            set({
              isReplayActive: true,
              replayIndex: idx,
              cityState: frame.cityState,
              summary: frame.summary,
              liveEvents: frame.liveEvents,
              conversations: frame.conversations,
            });
          }
        }
      } else {
        if (liveStateBackup) {
          set({
            isReplayActive: false,
            cityState: liveStateBackup.cityState,
            summary: liveStateBackup.summary,
            liveEvents: liveStateBackup.liveEvents,
            conversations: liveStateBackup.conversations,
          });
          liveStateBackup = null;
        } else {
          set({ isReplayActive: false });
        }
      }
    },

    scrubTimeline: (index) => {
      const buffer = get().replayBuffer;
      const frame = buffer[index];
      if (frame) {
        set({
          replayIndex: index,
          cityState: frame.cityState,
          summary: frame.summary,
          liveEvents: frame.liveEvents,
          conversations: frame.conversations,
        });
      }
    },

    cleanup: () => {
      if (pollInterval) clearInterval(pollInterval);
      if (eventRateInterval) clearInterval(eventRateInterval);
      eventsSocket?.close();
      approvalsSocket?.close();
    },
  };
});
