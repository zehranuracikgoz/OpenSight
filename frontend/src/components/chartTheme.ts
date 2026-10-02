import type { CSSProperties } from 'react';

// recharts ın varsayılan renkleri iki temada okunmuyor
const tickStyle = {
  fill: 'var(--color-text-secondary)',
  fontSize: 12,
  fontFamily:'var(--font-mono)',
};

export const axisProps = {
  tick: tickStyle,
  stroke: 'var(--color-chart-grid)',
};

export const gridProps = {
  strokeDasharray: '3 3',
  stroke: 'var(--color-chart-grid)',
};

export const tooltipProps = {
  contentStyle: {
    backgroundColor: 'var(--color-card-bg)',
    border: '1px solid var(--color-card-border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-primary)',
    fontFamily : 'var(--font-sans)',
  } satisfies CSSProperties,
  labelStyle: { color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' } satisfies CSSProperties,
  itemStyle : { color: 'var(--color-text-primary)' } satisfies CSSProperties,
};

export const legendProps = {
  wrapperStyle: { color: 'var(--color-text-secondary)', fontSize: 12 } satisfies CSSProperties,
};

export const COLORS = {
  latency: 'var(--color-chart-latency)',
  rate: 'var(--color-chart-rate)',
  // performans noktaları rozet rengini kullanıyo
  performanceAnomaly: 'var(--color-badge-performance-text)',
  correlation: 'var(--color-correlation)' ,
};