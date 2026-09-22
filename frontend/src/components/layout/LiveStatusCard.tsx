'use client';

import { cn } from '@/lib/utils';
import { LiveStatus } from '@/types';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { formatNumber } from '@/lib/utils';

interface LiveStatusProps {
  status: LiveStatus | null;
  isLoading?: boolean;
}

const statusItems = [
  { key: 'ingestionRate', label: 'Ingestion Rate', format: (v: number) => `${formatNumber(v)}/min` },
  { key: 'queueDepth', label: 'Queue Depth', format: (v: number) => formatNumber(v) },
  { key: 'activeNarratives', label: 'Active Narratives', format: (v: number) => formatNumber(v) },
  { key: 'openPositions', label: 'Open Positions', format: (v: number) => formatNumber(v) },
] as const;

export function LiveStatusCard({ status, isLoading }: LiveStatusProps) {
  if (isLoading || !status) {
    return (
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className="w-3 h-3 rounded-full bg-slate-200 dark:bg-slate-700 animate-pulse" />
            <div className="flex-1">
              <div className="h-4 w-1/4 bg-slate-200 dark:bg-slate-700 animate-pulse rounded" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="bordered">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-foreground">Live Status</h3>
          <Badge
            variant={status.isConnected ? 'success' : 'danger'}
            size="sm"
            className="gap-1.5"
          >
            <span
              className={cn(
                'w-2 h-2 rounded-full',
                status.isConnected ? 'bg-green-500' : 'bg-red-500'
              )}
            />
            {status.isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {statusItems.map((item) => (
            <div key={item.key} className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
                {item.label}
              </div>
              <div className="font-mono text-lg font-medium text-foreground">
                {item.format(status[item.key as keyof LiveStatus] as number)}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span>Last update: {new Date(status.lastUpdate).toLocaleTimeString()}</span>
          <Badge variant="outline" size="sm">
            {status.paperTrading ? 'Paper Trading' : 'Live Trading'}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}