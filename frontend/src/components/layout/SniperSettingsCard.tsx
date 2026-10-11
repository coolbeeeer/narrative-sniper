'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { AppConfig } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

type NumKey =
  | 'signal_position_size_usd'
  | 'signal_confidence_threshold'
  | 'signal_min_cluster_size'
  | 'signal_max_open_positions'
  | 'signal_cooldown_hours'
  | 'signal_take_profit_pct'
  | 'signal_stop_loss_pct';

const NUM_FIELDS: { key: NumKey; label: string; step: string; min?: string; helper: string }[] = [
  {
    key: 'signal_position_size_usd',
    label: 'How much to spend on each trade (USD)',
    step: '1',
    min: '0',
    helper: 'Every time the sniper buys, it spends this much pretend money.',
  },
  {
    key: 'signal_confidence_threshold',
    label: 'How sure it must be before buying',
    step: '0.01',
    min: '0',
    helper: '0.7 means "70% sure". Higher = pickier, fewer trades. Lower = more trades, more duds.',
  },
  {
    key: 'signal_min_cluster_size',
    label: 'Smallest crowd worth trading',
    step: '1',
    min: '1',
    helper: 'How many posts about the same coin it must see grouped together before that coin counts as a story worth trading.',
  },
  {
    key: 'signal_max_open_positions',
    label: 'Most trades open at the same time',
    step: '1',
    min: '1',
    helper: 'It will never hold more trades than this at once.',
  },
  {
    key: 'signal_cooldown_hours',
    label: 'Wait before buying the same coin again (hours)',
    step: '1',
    min: '0',
    helper: 'After trading a coin, it leaves that coin alone for this long.',
  },
  {
    key: 'signal_take_profit_pct',
    label: 'Sell when profit reaches (%)',
    step: '1',
    min: '0',
    helper: 'If a trade gains this much, it sells and banks the profit.',
  },
  {
    key: 'signal_stop_loss_pct',
    label: 'Sell when loss reaches (%)',
    step: '1',
    min: '0',
    helper: 'If a trade drops this much, it sells to stop the loss growing.',
  },
];

export function SniperSettingsCard() {
  const [config, setConfig] = useState<AppConfig | null>(null);  const [draft, setDraft] = useState<Partial<Record<NumKey, string>>>({});
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getConfig()
      .then((data: AppConfig) => {
        if (!cancelled) {
          setConfig(data);
          setDraft({});
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not load settings.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setDraftValue = (key: NumKey, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setSavedAt(null);
  };

  const isDirty = Object.keys(draft).length > 0;

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      const payload: Partial<AppConfig> = {};
      for (const key of Object.keys(draft) as NumKey[]) {
        const raw = draft[key];
        if (raw === undefined || raw === '') continue;
        const num = Number(raw);
        if (!Number.isFinite(num)) {
          throw new Error(`"${raw}" is not a valid number.`);
        }
        (payload as Record<string, number>)[key] = num;
      }
      const updated: AppConfig = await api.updateConfig(payload);
      setConfig(updated);
      setDraft({});
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setDraft({});
    setError(null);
  };

  // Effective value of a field: what the box currently shows (draft wins).
  const eff = (key: NumKey): number => {
    const raw = draft[key];
    if (raw !== undefined && raw !== '') {
      const n = Number(raw);
      if (Number.isFinite(n)) return n;
    }
    return config ? config[key] : 0;
  };

  return (
    <Card variant="bordered">
      <CardHeader>
        <CardTitle className="text-lg">Sniper Settings</CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Changes apply to the next trade, no restart needed.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        {!config && !error && (
          <p className="text-sm text-muted-foreground">Loading settings…</p>
        )}
        {config && (
          <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 p-3 text-sm leading-relaxed text-foreground">
            <span className="font-semibold">In plain words: </span>
            I watch for a coin that at least {eff('signal_min_cluster_size')} people are
            talking about at once. When I am at least{' '}
            {Math.round(eff('signal_confidence_threshold') * 100)}% sure it is a real
            story, I buy ${eff('signal_position_size_usd')} worth with pretend money. I
            sell when it gains {eff('signal_take_profit_pct')}% or drops{' '}
            {eff('signal_stop_loss_pct')}%, and I never hold more than{' '}
            {eff('signal_max_open_positions')} trades at the same time.
          </div>
        )}
        {config &&
                  NUM_FIELDS.map(({ key, label, step, min, helper }) => (
                    <Input
                      key={key}
                      label={label}
                      type="number"
                      step={step}
                      min={min}
                      helperText={helper}
                      value={draft[key] ?? String(config[key])}
                      onChange={(e) => setDraftValue(key, (e.target as HTMLInputElement).value)}
                    />
                  ))}
        {config && (
          <>
            <div className="flex items-center gap-2 pt-1">
              <Button variant="primary" size="sm" onClick={handleSave} loading={saving} disabled={!isDirty}>
                Save settings
              </Button>
              <Button variant="ghost" size="sm" onClick={handleReset} disabled={!isDirty || saving}>
                Reset
              </Button>
            </div>
            {savedAt && (
              <p className="text-xs text-muted-foreground">Saved at {savedAt}.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
