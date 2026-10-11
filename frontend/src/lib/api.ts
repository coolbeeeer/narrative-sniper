import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { Narrative, Position, PnLDataPoint, LiveStatus, PaginatedResponse, AppConfig } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

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
    const response = await this.client.get<PaginatedResponse<Narrative>>('/api/narratives', { params });
    return response.data;
  }

  async getNarrative(id: string) {
    const response = await this.client.get<Narrative>(`/api/narratives/${id}`);
    return response.data;
  }

  async getPositions(params?: { status?: string; narrativeId?: string }) {
    const response = await this.client.get<PaginatedResponse<Position>>('/api/positions', { params });
    return response.data;
  }

  async getPosition(id: string) {
    const response = await this.client.get<Position>(`/api/positions/${id}`);
    return response.data;
  }

  async getPnLHistory(range: '1h' | '24h' | '7d' | '30d' = '24h') {
    const response = await this.client.get<PnLDataPoint[]>('/api/pnl/history', { params: { range } });
    return response.data;
  }

  async getLiveStatus() {
    const response = await this.client.get<LiveStatus>('/api/status/live');
    return response.data;
  }

  async getConfig() {
    const response = await this.client.get('/api/config');
    return response.data;
  }

  async updateConfig(config: Partial<AppConfig>) {
    const response = await this.client.patch('/api/config', config);
    return response.data;
  }

  createWebSocket() {
    return new WebSocket(`${WS_BASE}/ws`);
  }
}

export const api = new ApiClient();