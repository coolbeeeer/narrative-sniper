import { cn } from '@/lib/utils';
import { Position } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Card, CardContent } from '@/components/ui/Card';
import { formatUsd, formatPercent, formatShortNumber, formatTimestamp, getPnlColor, getPnlBgColor } from '@/lib/utils';

interface PositionTableProps {
  positions: Position[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLoading?: boolean;
}

export function PositionTable({ positions, selectedId, onSelect, isLoading }: PositionTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="space-y-4" role="status" aria-label="Loading positions">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 animate-pulse bg-slate-100 dark:bg-slate-800 rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const safePositions = positions || [];
  if (safePositions.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <p className="text-muted-foreground">No open positions</p>
          <p className="text-sm text-muted-foreground/70 mt-1">Positions will appear here when narratives are traded</p>
        </CardContent>
      </Card>
    );
  }

  const openPositions = safePositions.filter((p) => p.status === 'open');
  const closedPositions = positions.filter((p) => p.status === 'closed');

  return (
    <Card variant="bordered">
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full" role="table">
            <thead>
              <tr className="border-b border-border bg-slate-50 dark:bg-slate-900/50">
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Token</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Narrative</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Entry</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Current</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Amount</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Value</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">PnL</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Entry Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {safePositions.map((position) => (
                <tr
                  key={position.id}
                  onClick={() => onSelect(position.id)}
                  className={cn(
                    'cursor-pointer transition-colors duration-150',
                    'hover:bg-slate-50 dark:hover:bg-slate-800/50',
                    selectedId === position.id && 'bg-copper-50 dark:bg-copper-900/20'
                  )}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(position.id)}
                  aria-selected={selectedId === position.id}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{position.tokenSymbol}</div>
                    <div className="text-sm text-muted-foreground truncate max-w-xs">{position.tokenName}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" size="sm">{position.narrativeLabel}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatUsd(position.entryPrice)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatUsd(position.currentPrice)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-muted-foreground">
                    {formatShortNumber(position.amount)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm font-medium text-foreground">
                    {formatUsd(position.valueUsd)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className={cn('font-mono text-sm font-medium', getPnlColor(position.pnlPercent))}>
                      {position.pnlUsd >= 0 ? '+' : ''}{formatUsd(position.pnlUsd)}
                    </div>
                    <div className={cn('font-mono text-xs', getPnlColor(position.pnlPercent))}>
                      {position.pnlPercent >= 0 ? '+' : ''}{formatPercent(position.pnlPercent)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={position.status === 'open' ? 'success' : position.status === 'partial' ? 'warning' : 'default'}
                      size="sm"
                    >
                      {position.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatTimestamp(position.entryTime)}
                  </td>
                </tr>
              ))}
              {closedPositions.map((position) => (
                <tr
                  key={position.id}
                  onClick={() => onSelect(position.id)}
                  className={cn(
                    'cursor-pointer transition-colors duration-150 opacity-60',
                    'hover:bg-slate-50 dark:hover:bg-slate-800/50',
                    selectedId === position.id && 'bg-copper-50 dark:bg-copper-900/20 opacity-100'
                  )}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(position.id)}
                  aria-selected={selectedId === position.id}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{position.tokenSymbol}</div>
                    <div className="text-sm text-muted-foreground truncate max-w-xs">{position.tokenName}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" size="sm">{position.narrativeLabel}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatUsd(position.entryPrice)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatUsd(position.currentPrice)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-muted-foreground">
                    {formatShortNumber(position.amount)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm font-medium text-foreground">
                    {formatUsd(position.valueUsd)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className={cn('font-mono text-sm font-medium', getPnlColor(position.pnlPercent))}>
                      {position.pnlUsd >= 0 ? '+' : ''}{formatUsd(position.pnlUsd)}
                    </div>
                    <div className={cn('font-mono text-xs', getPnlColor(position.pnlPercent))}>
                      {position.pnlPercent >= 0 ? '+' : ''}{formatPercent(position.pnlPercent)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="default" size="sm">closed</Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatTimestamp(position.entryTime)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}