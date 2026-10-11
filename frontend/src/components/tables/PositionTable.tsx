import { cn } from '@/lib/utils';
import { Position } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { formatUsd, formatPrice, formatPercent, formatShortNumber, formatTimestamp, getPnlColor, shortenAddress } from '@/lib/utils';

interface PositionTableProps {
  positions: Position[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLoading?: boolean;
}

export function PositionTable({ positions, selectedId, onSelect, isLoading }: PositionTableProps) {
  if (isLoading) {
    return (
      <div className="p-6">
        <div className="space-y-4" role="status" aria-label="Loading positions">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse bg-muted rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const safePositions = positions || [];
  if (safePositions.length === 0) {
    return (
      <div className="p-8 text-center">
        <p className="text-muted-foreground">No trades yet</p>
        <p className="text-sm text-muted-foreground/70 mt-1">A trade appears here when a story is strong enough and its coin passes the safety check (real trading activity, not a scam).</p>
      </div>
    );
  }

  const openPositions = safePositions.filter((p) => p.status === 'open');
  const closedPositions = positions.filter((p) => p.status === 'closed');

  return (
    <div className="overflow-x-auto">
          <table className="w-full min-w-[960px]" role="table">
            <thead>
              <tr className="border-b border-border bg-muted/60">
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Coin</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Story</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Bought at</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Price now</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Coins held</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Worth now</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider">Profit / loss</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Bought</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {openPositions.map((position) => (
                <tr
                  key={position.id}
                  onClick={() => onSelect(position.id)}
                  className={cn(
                    'cursor-pointer transition-colors duration-150',
                    'hover:bg-muted/50',
                    selectedId === position.id && 'bg-copper-500/10'
                  )}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(position.id)}
                  aria-selected={selectedId === position.id}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{position.tokenSymbol}</div>
                    <div className="text-sm text-muted-foreground leading-snug">{position.tokenName}</div>
                    {position.tokenAddress && (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        CA:{' '}
                        <a
                          href={`https://dexscreener.com/solana/${position.tokenAddress}`}
                          target="_blank"
                          rel="noreferrer"
                          title={position.tokenAddress}
                          onClick={(e) => e.stopPropagation()}
                          className="font-mono text-copper-400 hover:underline"
                        >
                          {shortenAddress(position.tokenAddress)}
                        </a>
                      </div>
                    )}
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Bought {formatTimestamp(position.entryTime)}
                    </div>
                    {position.entryMarketCap ? (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        at <span className="font-medium text-foreground">{formatUsd(position.entryMarketCap)}</span> market cap
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" size="sm">{position.narrativeLabel}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatPrice(position.entryPrice)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatPrice(position.currentPrice)}
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
                      {position.status === 'open' ? 'Open' : position.status === 'partial' ? 'Partly sold' : 'Sold'}
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
                    'hover:bg-muted/50',
                    selectedId === position.id && 'bg-copper-500/10 opacity-100'
                  )}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(position.id)}
                  aria-selected={selectedId === position.id}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{position.tokenSymbol}</div>
                    <div className="text-sm text-muted-foreground leading-snug">{position.tokenName}</div>
                    {position.tokenAddress && (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        CA:{' '}
                        <a
                          href={`https://dexscreener.com/solana/${position.tokenAddress}`}
                          target="_blank"
                          rel="noreferrer"
                          title={position.tokenAddress}
                          onClick={(e) => e.stopPropagation()}
                          className="font-mono text-copper-400 hover:underline"
                        >
                          {shortenAddress(position.tokenAddress)}
                        </a>
                      </div>
                    )}
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Bought {formatTimestamp(position.entryTime)}
                    </div>
                    {position.entryMarketCap ? (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        at <span className="font-medium text-foreground">{formatUsd(position.entryMarketCap)}</span> market cap
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" size="sm">{position.narrativeLabel}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatPrice(position.entryPrice)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-foreground">
                    {formatPrice(position.currentPrice)}
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
                    <Badge variant="default" size="sm">Sold</Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatTimestamp(position.entryTime)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
    </div>
  );
}