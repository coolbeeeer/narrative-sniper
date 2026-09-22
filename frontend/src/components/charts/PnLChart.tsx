'use client';

import { cn } from '@/lib/utils';
import { PnLDataPoint } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
} from 'recharts';

interface PnLChartProps {
  data: PnLDataPoint[];
  isLoading?: boolean;
}

export function PnLChart({ data, isLoading }: PnLChartProps) {
  if (isLoading || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>PnL History</CardTitle>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <div className="text-muted-foreground">
            {isLoading ? 'Loading PnL data...' : 'No PnL data available'}
          </div>
        </CardContent>
      </Card>
    );
  }

  const latest = data[data.length - 1];
  const first = data[0];
  const totalChange = latest.totalValue - first.totalValue;
  const totalChangePercent = ((totalChange / first.totalValue) * 100).toFixed(2);

  const formatValue = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Portfolio Value</CardTitle>
        <div className={cn('font-mono text-sm font-medium', totalChange >= 0 ? 'text-green-600' : 'text-red-600')}>
          {formatValue(latest.totalValue)}
          <span className="ml-2 text-xs">
            {totalChange >= 0 ? '+' : ''}{formatValue(totalChange)} ({totalChangePercent}%)
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64" role="img" aria-label="Portfolio value over time">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatTime}
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                axisLine={{ stroke: 'hsl(var(--border))' }}
                tickLine={false}
              />
              <YAxis
                tickFormatter={formatValue}
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={60}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                }}
                labelFormatter={formatTime}
                formatter={(value: number) => [formatValue(value), 'Portfolio Value']}
              />
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorUnrealized" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="totalValue"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorValue)"
              />
              <Line
                type="monotone"
                dataKey="unrealizedPnl"
                stroke="hsl(var(--primary))"
                strokeWidth={1}
                strokeDasharray="5 5"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-copper-500" />
              Total Value
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-copper-500" style={{ opacity: 0.5 }} />
              Unrealized PnL
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-green-600 font-mono">
              Realized: {latest.realizedPnl >= 0 ? '+' : ''}{formatValue(latest.realizedPnl)}
            </span>
            <span className={cn('font-mono', latest.unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600')}>
              Unrealized: {latest.unrealizedPnl >= 0 ? '+' : ''}{formatValue(latest.unrealizedPnl)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}