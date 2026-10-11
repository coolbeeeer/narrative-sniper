export interface Narrative {
  id: string;
  label: string;
  description: string;
  confidence: number;
  clusterSize: number;
  topTokens: string[];
  sources: SourceRef[];
  tokenMint?: string | null;
  tokenSymbol?: string | null;
  tokenName?: string | null;
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

export interface AppConfig {
  paper_trading: boolean;
  max_position_size_usd: number;
  max_daily_loss_usd: number;
  slippage_bps: number;
  priority_fee_lamports: number;
  narrative_confidence_threshold: number;
  signal_enabled: boolean;
  signal_confidence_threshold: number;
  signal_min_cluster_size: number;
  signal_position_size_usd: number;
  signal_max_open_positions: number;
  signal_cooldown_hours: number;
  signal_take_profit_pct: number;
  signal_stop_loss_pct: number;
}