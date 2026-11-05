export type VaTone = 'positive' | 'negative' | 'neutral';

/** Value added with an explicit sign, e.g. "+0.50", "−1.25". */
export function formatVa(value: number | null | undefined): string {
  if (value == null) return '–';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toFixed(2)}`;
}

/** Positive / negative when |VA| reaches the significance threshold (SRS 3.5). */
export function vaTone(value: number | null | undefined, threshold: number): VaTone {
  if (value == null) return 'neutral';
  if (value >= threshold) return 'positive';
  if (value <= -threshold) return 'negative';
  return 'neutral';
}
