export interface Narrative {
  id: string;
  label: string;
  description: string;
  confidence: number;
  clusterSize: number;
  topTokens: string[];
  sources: SourceRef[];
  createdAt: string;
  updatedAt: string;
}

export interface SourceRef {
  platform: 'twitter' | 'telegram' | 'discord' | 'helius';
  handle: string;
  url: string;
  timestamp: string;
  engagement: number;
}

export interface Position {
  id: string;
  tokenAddress: string;
  tokenSymbol: string;
  tokenName: string;
  entryPrice: number;
  currentPrice: number;
  amount: number;
  valueUsd: number;
  pnlUsd: number;
  pnlPercent: number;
  narrativeId: string;
  narrativeLabel: string;
  entryTime: string;
  status: 'open' | 'closed' | 'partial';
  txSignature?: string;
}

export interface PnLDataPoint {
  timestamp: string;
  totalValue: number;
  realizedPnl: number;
  unrealizedPnl: number;
}

export interface LiveStatus {
  isConnected: boolean;
  lastUpdate: string;
  ingestionRate: number;
  queueDepth: number;
  activeNarratives: number;
  openPositions: number;
  paperTrading: boolean;
}

export interface ApiResponse<T> {
  data: T;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}