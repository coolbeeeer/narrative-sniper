'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { AppConfig, WalletStatus } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatUsd, shortenAddress } from '@/lib/utils';

export function WalletCard() {
  const [wallet, setWallet] = useState<WalletStatus | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [w, c] = await Promise.all([api.getWalletStatus(), api.getConfig()]);
      setWallet(w);
      setConfig(c);
    } catch {
      // Wallet status is best-effort UI; the card explains itself below.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const live = !!config?.live_trading_enabled;

  const toggle = async (enabled: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.setLiveTrading(enabled);
      setConfig(updated);
      setConfirming(false);
      await refresh();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'The switch could not be changed. Is the backend running?');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card variant="bordered">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">Bot wallet</CardTitle>
        <Badge variant={live ? 'danger' : 'outline'} size="md">
          {live ? '● LIVE — real money' : 'Paper money'}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {!wallet ? (
          <p className="text-sm text-muted-foreground">Checking the wallet…</p>
        ) : !wallet.configured ? (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              No bot wallet is set up yet, so the sniper can only trade with pretend money.
            </p>
            <p className="text-sm text-muted-foreground">
              To create one, run <span className="font-mono text-foreground">python -m app.live.wallet</span> in the
              backend folder, paste the secret it shows into <span className="font-mono text-foreground">BOT_WALLET_PRIVATE_KEY</span> in
              the backend <span className="font-mono text-foreground">.env</span> file, restart the backend, and send a
              small amount of SOL to the wallet address it printed.
            </p>
          </div>
        ) : (
          <>
            <div>
              <div className="text-sm text-muted-foreground">Wallet address</div>
              <div className="font-mono text-sm text-foreground" title={wallet.address ?? undefined}>
                {wallet.address ? shortenAddress(wallet.address) : '—'}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Send SOL to this address to fund live trading. Only ever keep what the sniper is allowed to lose in it.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-muted-foreground">SOL balance</div>
                <div className="font-mono text-xl font-semibold text-foreground">
                  {wallet.sol_balance === null || wallet.sol_balance === undefined
                    ? '—'
                    : wallet.sol_balance.toFixed(4)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Daily loss limit</div>
                <div className="font-mono text-xl font-semibold text-foreground">
                  {config ? formatUsd(config.live_daily_loss_limit_usd) : '—'}
                </div>
              </div>
            </div>

            {error && <p className="text-sm text-red-500">{error}</p>}

            {live ? (
              <div className="space-y-2">
                <p className="text-sm text-red-500 font-medium">
                  Live trading is ON. Every trade the sniper makes now spends real SOL from this wallet.
                </p>
                <Button variant="outline" size="sm" disabled={busy} onClick={() => toggle(false)}>
                  Switch back to paper money
                </Button>
              </div>
            ) : confirming ? (
              <div className="space-y-2 rounded-md border border-red-500/40 bg-red-500/10 p-3">
                <p className="text-sm text-foreground">
                  Switch to <strong>real money</strong>? The sniper will buy and sell with actual SOL from this
                  wallet, at the sizes and rules in Sniper Settings. The safety check and the daily loss limit
                  still apply.
                </p>
                <div className="flex gap-2">
                  <Button variant="destructive" size="sm" disabled={busy} onClick={() => toggle(true)}>
                    Yes — trade with real money
                  </Button>
                  <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirming(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="destructive" size="sm" disabled={busy} onClick={() => setConfirming(true)}>
                Switch to LIVE trading
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
