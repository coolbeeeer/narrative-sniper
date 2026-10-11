import { cn } from '@/lib/utils';
import { Narrative } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Card, CardContent } from '@/components/ui/Card';
import { formatUsd, formatNumber, formatShortNumber, formatTimestamp, getPnlColor } from '@/lib/utils';

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
          <p className="text-muted-foreground">No narratives detected yet</p>
          <p className="text-sm text-muted-foreground/70 mt-1">Start ingestion to discover emerging narratives</p>
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
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Narrative</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Confidence</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Cluster Size</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Top Tokens</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Sources</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Updated</th>
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
                    <div className="text-sm text-muted-foreground truncate max-w-xs">{narrative.description}</div>
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
                    {sources.length} sources
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