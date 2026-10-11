'use client';

import { cn } from '@/lib/utils';
import { LiveStatus } from '@/types';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
interface LiveStatusProps {
  status: LiveStatus | null;
  isLoading?: boolean;
}

const whole = (v: number) => Math.round(v).toLocaleString('en-US');

const statusItems = [
  { key: 'ingestionRate', label: 'Posts seen per min', format: whole },
  { key: 'queueDepth', label: 'Waiting to be checked', format: whole },
  { key: 'activeNarratives', label: 'Stories found', format: whole },
  { key: 'openPositions', label: 'Trades open now', format: whole },
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
            {status.isConnected ? 'Working' : 'Not connected'}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {statusItems.map((item) => (
            <div key={item.key} className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
                {item.label}
              </div>
              <div className="font-mono text-lg font-medium text-foreground truncate" title={String(status[item.key as keyof LiveStatus])}>
                {item.format(status[item.key as keyof LiveStatus] as number)}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span>Last checked: {new Date(status.lastUpdate).toLocaleTimeString()}</span>
          <Badge variant="outline" size="sm">
            {status.paperTrading ? 'Practice money' : 'Real money'}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}