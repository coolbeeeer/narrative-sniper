import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay: 'exceptZero',
  }).format(value / 100);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatShortNumber(value: number): string {
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
  return value.toFixed(2);
}

/** Shorten a Solana address for display: AbCd…WxYz (full value in title). */
export function shortenAddress(address: string): string {
  if (!address || address.length <= 10) return address;
  return `${address.slice(0, 4)}…${address.slice(-4)}`;
}

export function formatTimestamp(timestamp: string): string {
  // Backend timestamps are UTC but carry no timezone marker; without this
  // the browser would read them as local time and show the wrong hour.
  const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(timestamp.trim());
  const date = new Date(hasTz ? timestamp : `${timestamp}Z`);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Price display that survives tiny meme-coin prices ($0.00 is useless). */
export function formatPrice(value: number): string {
  if (!value) return '$0.00';
  if (Math.abs(value) >= 0.01) return formatUsd(value);
  return `$${parseFloat(value.toPrecision(4)).toString()}`;
}

export function getPnlColor(pnl: number): string {
  if (pnl > 0) return 'text-green-600 dark:text-green-400';
  if (pnl < 0) return 'text-red-600 dark:text-red-400';
  return 'text-muted-foreground';
}

export function getPnlBgColor(pnl: number): string {
  if (pnl > 0) return 'bg-green-100 dark:bg-green-900/30';
  if (pnl < 0) return 'bg-red-100 dark:bg-red-900/30';
  return 'bg-muted';
}