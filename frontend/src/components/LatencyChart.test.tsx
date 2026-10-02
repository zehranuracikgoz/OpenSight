import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LatencyChart } from './LatencyChart';

describe('LatencyChart', () => {
  it('örnek (mock) veriyle çizildiğini belirten notu gösteriyor', () => {
    render(<LatencyChart />) ;

    expect(screen.getByText( 'grafik şimdilik örnek (mock) veriyle çiziliyor')).toBeInTheDocument();
  
  });
});