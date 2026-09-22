import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Narrative, Position, PnLDataPoint, LiveStatus } from '@/types';
import { api } from '@/lib/api';

interface AppState {
  narratives: Narrative[];
  positions: Position[];
  pnlHistory: PnLDataPoint[];
  liveStatus: LiveStatus | null;
  isLoading: boolean;
  error: string | null;
  ws: WebSocket | null;
  selectedNarrativeId: string | null;
  selectedPositionId: string | null;
  timeRange: '1h' | '24h' | '7d' | '30d';

  fetchNarratives: () => Promise<void>;
  fetchPositions: () => Promise<void>;
  fetchPnLHistory: () => Promise<void>;
  fetchLiveStatus: () => Promise<void>;
  connectWebSocket: () => void;
  disconnectWebSocket: () => void;
  setSelectedNarrative: (id: string | null) => void;
  setSelectedPosition: (id: string | null) => void;
  setTimeRange: (range: '1h' | '24h' | '7d' | '30d') => void;
  setError: (error: string | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      narratives: [],
      positions: [],
      pnlHistory: [],
      liveStatus: null,
      isLoading: false,
      error: null,
      ws: null,
      selectedNarrativeId: null,
      selectedPositionId: null,
      timeRange: '24h',

      fetchNarratives: async () => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.getNarratives();
          set({ narratives: response.items, isLoading: false });
        } catch (error) {
          set({ error: 'Failed to fetch narratives', isLoading: false });
        }
      },

      fetchPositions: async () => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.getPositions();
          set({ positions: response.items, isLoading: false });
        } catch (error) {
          set({ error: 'Failed to fetch positions', isLoading: false });
        }
      },

      fetchPnLHistory: async () => {
        set({ isLoading: true, error: null });
        try {
          const data = await api.getPnLHistory(get().timeRange);
          set({ pnlHistory: data, isLoading: false });
        } catch (error) {
          set({ error: 'Failed to fetch PnL history', isLoading: false });
        }
      },

      fetchLiveStatus: async () => {
        try {
          const status = await api.getLiveStatus();
          set({ liveStatus: status });
        } catch (error) {
          set({ liveStatus: null });
        }
      },

      connectWebSocket: () => {
        if (get().ws?.readyState === WebSocket.OPEN) return;

        const ws = api.createWebSocket();
        ws.onopen = () => {
          get().fetchLiveStatus();
        };
        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            switch (message.type) {
              case 'status':
                set({ liveStatus: message.data });
                break;
              case 'narrative_update':
                set((state) => ({
                  narratives: state.narratives.map((n) =>
                    n.id === message.data.id ? message.data : n
                  ),
                }));
                break;
              case 'position_update':
                set((state) => ({
                  positions: state.positions.map((p) =>
                    p.id === message.data.id ? message.data : p
                  ),
                }));
                break;
              case 'pnl_update':
                set((state) => ({
                  pnlHistory: [...state.pnlHistory.slice(-100), message.data],
                }));
                break;
            }
          } catch (error) {
            console.error('WS message parse error:', error);
          }
        };
        ws.onclose = () => {
          setTimeout(() => get().connectWebSocket(), 5000);
        };
        ws.onerror = (error) => {
          console.error('WS error:', error);
        };

        set({ ws });
      },

      disconnectWebSocket: () => {
        get().ws?.close();
        set({ ws: null });
      },

      setSelectedNarrative: (id) => set({ selectedNarrativeId: id }),
      setSelectedPosition: (id) => set({ selectedPositionId: id }),
      setTimeRange: (range) => {
        set({ timeRange: range });
        get().fetchPnLHistory();
      },
      setError: (error) => set({ error }),
    }),
    {
      name: 'narrative-sniper-store',
      partialize: (state) => ({
        selectedNarrativeId: state.selectedNarrativeId,
        selectedPositionId: state.selectedPositionId,
        timeRange: state.timeRange,
      }),
    }
  )
);