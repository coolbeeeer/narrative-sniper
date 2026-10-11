import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { Narrative, Position, PnLDataPoint, LiveStatus, SourceRef, AppConfig } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

type Raw = Record<string, any>;

const pick = (obj: Raw | undefined | null, camel: string, snake: string) =>
  obj?.[camel] ?? obj?.[snake];

export function mapSourceRef(raw: Raw): SourceRef {
  return {
    platform: raw?.platform ?? 'twitter',
    handle: raw?.handle ?? '',
    url: raw?.url ?? '',
    timestamp: raw?.timestamp ?? '',
    engagement: raw?.engagement ?? 0,
  };
}

export function mapNarrative(raw: Raw): Narrative {
  return {
    id: raw?.id ?? '',
    label: raw?.label ?? '',
    description: raw?.description ?? '',
    confidence: raw?.confidence ?? 0,
    clusterSize: pick(raw, 'clusterSize', 'cluster_size') ?? 0,
    topTokens: pick(raw, 'topTokens', 'top_tokens') ?? [],
    sources: (raw?.sources ?? []).map(mapSourceRef),
    tokenMint: pick(raw, 'tokenMint', 'token_mint') ?? null,
    tokenSymbol: pick(raw, 'tokenSymbol', 'token_symbol') ?? null,
    tokenName: pick(raw, 'tokenName', 'token_name') ?? null,
    tradeStatus: pick(raw, 'tradeStatus', 'trade_status') ?? null,
    tradeReason: pick(raw, 'tradeReason', 'trade_reason') ?? null,
    caughtMarketCap: pick(raw, 'caughtMarketCap', 'caught_market_cap') ?? null,
    createdAt: pick(raw, 'createdAt', 'created_at') ?? '',
    updatedAt: pick(raw, 'updatedAt', 'updated_at') ?? '',
  };
}

export function mapPosition(raw: Raw): Position {
  return {
    id: raw?.id ?? '',
    tokenAddress: pick(raw, 'tokenAddress', 'token_address') ?? '',
    tokenSymbol: pick(raw, 'tokenSymbol', 'token_symbol') ?? '',
    tokenName: pick(raw, 'tokenName', 'token_name') ?? '',
    entryPrice: pick(raw, 'entryPrice', 'entry_price') ?? 0,
    currentPrice: pick(raw, 'currentPrice', 'current_price') ?? 0,
    amount: raw?.amount ?? 0,
    valueUsd: pick(raw, 'valueUsd', 'value_usd') ?? 0,
    pnlUsd: pick(raw, 'pnlUsd', 'pnl_usd') ?? 0,
    pnlPercent: pick(raw, 'pnlPercent', 'pnl_percent') ?? 0,
    narrativeId: pick(raw, 'narrativeId', 'narrative_id') ?? '',
    narrativeLabel: pick(raw, 'narrativeLabel', 'narrative_label') ?? '',
    entryTime: pick(raw, 'entryTime', 'entry_time') ?? '',
    entryMarketCap: pick(raw, 'entryMarketCap', 'entry_market_cap') ?? null,
    status: raw?.status ?? 'open',
    txSignature: pick(raw, 'txSignature', 'tx_signature'),
  };
}

export function mapPnLDataPoint(raw: Raw): PnLDataPoint {
  return {
    timestamp: raw?.timestamp ?? '',
    totalValue: pick(raw, 'totalValue', 'total_value') ?? 0,
    realizedPnl: pick(raw, 'realizedPnl', 'realized_pnl') ?? 0,
    unrealizedPnl: pick(raw, 'unrealizedPnl', 'unrealized_pnl') ?? 0,
  };
}

export function mapLiveStatus(raw: Raw): LiveStatus {
  return {
    isConnected: pick(raw, 'isConnected', 'is_connected') ?? false,
    lastUpdate: pick(raw, 'lastUpdate', 'last_update') ?? '',
    ingestionRate: pick(raw, 'ingestionRate', 'ingestion_rate') ?? 0,
    queueDepth: pick(raw, 'queueDepth', 'queue_depth') ?? 0,
    activeNarratives: pick(raw, 'activeNarratives', 'active_narratives') ?? 0,
    openPositions: pick(raw, 'openPositions', 'open_positions') ?? 0,
    paperTrading: pick(raw, 'paperTrading', 'paper_trading') ?? false,
  };
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' },
    });

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          if (typeof window !== 'undefined') {
            localStorage.removeItem('auth_token');
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  async getNarratives(params?: { page?: number; pageSize?: number; minConfidence?: number }) {
    const response = await this.client.get<Raw[]>('/api/narratives', { params });
    return response.data.map(mapNarrative);
  }

  async getNarrative(id: string) {
    const response = await this.client.get<Raw>(`/api/narratives/${id}`);
    return mapNarrative(response.data);
  }

  async getPositions(params?: { status?: string; narrativeId?: string }) {
    const response = await this.client.get<Raw[]>('/api/positions', { params });
    return response.data.map(mapPosition);
  }

  async getPosition(id: string) {
    const response = await this.client.get<Raw>(`/api/positions/${id}`);
    return mapPosition(response.data);
  }

  async getPnLHistory(range: '1h' | '24h' | '7d' | '30d' = '24h') {
    const response = await this.client.get<Raw[]>('/api/pnl/history', { params: { range } });
    return response.data.map(mapPnLDataPoint);
  }

  async getLiveStatus() {
    const response = await this.client.get<Raw>('/api/status/live');
    return mapLiveStatus(response.data);
  }

  async getConfig() {
    const response = await this.client.get('/api/config');
    return response.data;
  }

  async updateConfig(config: Partial<AppConfig>) {
    const response = await this.client.patch('/api/config', config);
    return response.data;
  }

  async getWalletStatus() {
    const response = await this.client.get('/api/wallet/status');
    return response.data;
  }

  async setLiveTrading(enabled: boolean) {
    const response = await this.client.patch('/api/config', {
      live_trading_enabled: enabled,
      ...(enabled ? { confirm_live: 'LIVE' } : {}),
    });
    return response.data;
  }

  createWebSocket() {
    return new WebSocket(`${WS_BASE}/ws`);
  }
}

export const api = new ApiClient();