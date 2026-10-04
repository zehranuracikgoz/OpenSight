import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { LatencySeries } from '../api/types';
import { LatencyChart } from './LatencyChart';

const emptySeries: LatencySeries = {
  minutes: 30,
  client_id: null,
  points: [],
  average_latency_ms: null,
  request_count: 0,
};

describe('LatencyChart', () => {
  it('trafik yokken boş durum metnini gösteriyor', () => {
    render(<LatencyChart series={emptySeries} alerts={[]} correlations={[]} />);

    expect(screen.getByText('Son 30 dakikada trafik yok — canlı demoyu başlatın.')).toBeInTheDocument();
  });
});
