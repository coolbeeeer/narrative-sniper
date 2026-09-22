'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/hooks/useAppStore';
import { NarrativeTable } from '@/components/tables/NarrativeTable';
import { PositionTable } from '@/components/tables/PositionTable';
import { PnLChart } from '@/components/charts/PnLChart';
import { LiveStatusCard } from '@/components/layout/LiveStatusCard';
import { SniperSettingsCard } from '@/components/layout/SniperSettingsCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatUsd, formatPercent } from '@/lib/utils';

export default function DashboardPage() {
  const {
    narratives,
    positions,
    pnlHistory,
    liveStatus,
    isLoading,
    error,
    selectedNarrativeId,
    selectedPositionId,
    fetchNarratives,
    fetchPositions,
    fetchPnLHistory,
    fetchLiveStatus,
    connectWebSocket,
    setSelectedNarrative,
    setSelectedPosition,
  } = useAppStore();

  useEffect(() => {
    fetchNarratives();
    fetchPositions();
    fetchPnLHistory();
    fetchLiveStatus();
    connectWebSocket();

    const interval = setInterval(() => {
      fetchLiveStatus();
    }, 10000);

    return () => {
      clearInterval(interval);
    };
  }, [fetchNarratives, fetchPositions, fetchPnLHistory, fetchLiveStatus, connectWebSocket]);

  const openPositions = positions.filter((p) => p.status === 'open');
  const totalValue = openPositions.reduce((sum, p) => sum + p.valueUsd, 0);
  const totalPnl = openPositions.reduce((sum, p) => sum + p.pnlUsd, 0);
  const totalPnlPercent = totalValue > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0;

  return (
    <div className="min-h-screen bg-background p-4 md:p-6 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Narrative Sniper</h1>
            <p className="text-muted-foreground mt-1">Real-time narrative detection & trading dashboard</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={liveStatus?.isConnected ? 'success' : 'danger'} size="md">
              {liveStatus?.isConnected ? '● Live' : '○ Offline'}
            </Badge>
            <Badge variant="outline" size="md">
              {liveStatus?.paperTrading ? 'Paper Trading' : 'Live Trading'}
            </Badge>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1 space-y-6">
            <LiveStatusCard status={liveStatus} isLoading={isLoading} />
            <SniperSettingsCard />
            <Card variant="bordered">
              <CardHeader>
                <CardTitle className="text-lg">Portfolio Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="text-sm text-muted-foreground">Total Value</div>
                  <div className="text-2xl font-bold font-mono text-foreground">{formatUsd(totalValue)}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Unrealized PnL</div>
                  <div className={`text-2xl font-bold font-mono ${totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {totalPnl >= 0 ? '+' : ''}{formatUsd(totalPnl)} ({totalPnlPercent >= 0 ? '+' : ''}{formatPercent(totalPnlPercent)})
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div>
                    <div className="text-xs text-muted-foreground">Open Positions</div>
                    <div className="font-mono text-xl font-semibold text-foreground">{openPositions.length}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Active Narratives</div>
                    <div className="font-mono text-xl font-semibold text-foreground">{narratives.length}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-3 space-y-6">
            <Card variant="bordered">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>PnL History</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" size="sm" className={!selectedNarrativeId ? 'bg-copper-50' : ''}>
                    All Narratives
                  </Badge>
                  {selectedNarrativeId && (
                    <Button variant="ghost" size="sm" onClick={() => setSelectedNarrative(null)}>
                      Clear Filter
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <PnLChart data={pnlHistory} isLoading={isLoading} />
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card variant="bordered">
                <CardHeader>
                  <CardTitle>Narratives</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">{narratives.length} detected</p>
                </CardHeader>
                <CardContent className="p-0">
                  <NarrativeTable
                    narratives={narratives}
                    selectedId={selectedNarrativeId}
                    onSelect={setSelectedNarrative}
                    isLoading={isLoading}
                  />
                </CardContent>
              </Card>

              <Card variant="bordered">
                <CardHeader>
                  <CardTitle>Positions</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">{openPositions.length} open, {positions.length - openPositions.length} closed</p>
                </CardHeader>
                <CardContent className="p-0">
                  <PositionTable
                    positions={positions}
                    selectedId={selectedPositionId}
                    onSelect={setSelectedPosition}
                    isLoading={isLoading}
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}