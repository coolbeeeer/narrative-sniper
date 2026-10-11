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
    label: 'Snipe amount per trade (USD)',
    step: '1',
    min: '0',
    helper: 'How much the sniper puts into each trade. Applies instantly.',
  },
  {
    key: 'signal_confidence_threshold',
    label: 'Confidence threshold',
    step: '0.01',
    min: '0',
    helper: 'Only narratives scoring above this open trades (0-1).',
  },
  {
    key: 'signal_min_cluster_size',
    label: 'Min cluster size',
    step: '1',
    min: '1',
    helper: 'Minimum mentions for a narrative to be tradeable.',
  },
  {
    key: 'signal_max_open_positions',
    label: 'Max open positions',
    step: '1',
    min: '1',
    helper: 'Hard cap on concurrent sniper positions.',
  },
  {
    key: 'signal_cooldown_hours',
    label: 'Cooldown (hours)',
    step: '1',
    min: '0',
    helper: 'Wait time before re-entering the same token.',
  },
  {
    key: 'signal_take_profit_pct',
    label: 'Take profit (%)',
    step: '1',
    min: '0',
    helper: 'Auto-close a position at this gain.',
  },
  {
    key: 'signal_stop_loss_pct',
    label: 'Stop loss (%)',
    step: '1',
    min: '0',
    helper: 'Auto-close a position at this loss.',
  },
];

export function SniperSettingsCard() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [draft, setDraft] = useState<Partial<Record<NumKey, string>>>({});
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
        {config &&
                  NUM_FIELDS.map(({ key, label, step, min, helper }) => (
                    <Input
                      key={key}
                      label={label}
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
