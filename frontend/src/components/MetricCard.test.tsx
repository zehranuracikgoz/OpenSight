import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MetricCard } from './MetricCard';

describe('MetricCard', ()=> {
  it('etiketi ve değeri gösteriyor', () => {
    render(<MetricCard label="Aktif Alert" value={5} />);

    expect(screen.getByText('Aktif Alert')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });
});