import { cn } from '@/lib/utils';
import { Narrative } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Card, CardContent } from '@/components/ui/Card';
import { formatUsd, formatNumber, formatShortNumber, formatTimestamp, getPnlColor, shortenAddress } from '@/lib/utils';

interface NarrativeTableProps {
  narratives: Narrative[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLoading?: boolean;
}

export function NarrativeTable({ narratives, selectedId, onSelect, isLoading }: NarrativeTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="space-y-4" role="status" aria-label="Loading narratives">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 animate-pulse bg-slate-100 dark:bg-slate-800 rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const safeNarratives = narratives || [];
  if (safeNarratives.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <p className="text-muted-foreground">No stories found yet</p>
          <p className="text-sm text-muted-foreground/70 mt-1">The sniper is listening. A story appears here when a crowd starts talking about the same coin at the same time.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="bordered">
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full" role="table">
            <thead>
              <tr className="border-b border-border bg-slate-50 dark:bg-slate-900/50">
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Story</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">How sure</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">People talking</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Coins mentioned</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Posts seen</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Last seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {safeNarratives.map((narrative) => {
                const topTokens = narrative.topTokens ?? [];
                const sources = narrative.sources ?? [];
                return (
                <tr
                  key={narrative.id}
                  onClick={() => onSelect(narrative.id)}
                  className={cn(
                    'cursor-pointer transition-colors duration-150',
                    'hover:bg-slate-50 dark:hover:bg-slate-800/50',
                    selectedId === narrative.id && 'bg-copper-50 dark:bg-copper-900/20'
                  )}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(narrative.id)}
                  aria-selected={selectedId === narrative.id}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{narrative.label}</div>
                    <div className="text-sm text-muted-foreground truncate max-w-xs">
                      {sources.some((s) => s.platform === 'dexscreener')
                        ? `${narrative.clusterSize} buys in the last hour`
                        : `${narrative.clusterSize} posts${topTokens.length > 0 ? ` talking about ${topTokens.slice(0, 3).join(', ')}` : ' in this story'}`}
                    </div>
                    {narrative.tokenMint ? (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        CA:{' '}
                        <a
                          href={`https://dexscreener.com/solana/${narrative.tokenMint}`}
                          target="_blank"
                          rel="noreferrer"
                          title={narrative.tokenMint}
                          onClick={(e) => e.stopPropagation()}
                          className="font-mono text-copper-600 hover:underline"
                        >
                          {shortenAddress(narrative.tokenMint)}
                        </a>
                      </div>
                    ) : (
                      <div className="text-xs text-muted-foreground/70 mt-0.5">CA: not pinned down yet</div>
                    )}
                    {narrative.tradeStatus === 'traded' ? (
                      <div className="text-xs font-medium text-green-600 dark:text-green-400 mt-1" title={narrative.tradeReason ?? undefined}>
                        Traded ✓ {narrative.tradeReason}
                      </div>
                    ) : narrative.tradeStatus === 'not_traded' ? (
                      <div className="text-xs text-amber-600 dark:text-amber-400 mt-1 max-w-xs" title={narrative.tradeReason ?? undefined}>
                        Not traded: {narrative.tradeReason}
                      </div>
                    ) : (
                      <div className="text-xs text-muted-foreground/70 mt-1">Being judged…</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={narrative.confidence >= 0.8 ? 'success' : narrative.confidence >= 0.6 ? 'info' : 'warning'}
                      size="sm"
                    >
                      {(narrative.confidence * 100).toFixed(0)}%
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-foreground">
                    {formatNumber(narrative.clusterSize)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {topTokens.slice(0, 3).map((token, i) => (
                        <Badge key={i} variant="outline" size="sm">
                          {token}
                        </Badge>
                      ))}
                      {topTokens.length > 3 && (
                        <Badge variant="outline" size="sm">
                          +{topTokens.length - 3}
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {sources.length} posts
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatTimestamp(narrative.updatedAt)}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}