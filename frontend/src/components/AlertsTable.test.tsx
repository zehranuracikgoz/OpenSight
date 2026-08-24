import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { AlertListItem } from '../api/types';
import { AlertsTable } from './AlertsTable';

const sampleAlerts: AlertListItem[] = [
  {
    alertId: '1',
    clientId: 'client_a',
    type: 'Performans',
    severity: 'Yüksek',
    createdAt: '2026-01-01T10:00:00Z',
  },
  {
    alertId: '2',
    clientId: 'client_b',
    type: 'Davranışsal',
    severity: 'Orta',
    createdAt: '2026-01-01T10:05:00Z' ,
  },
];

describe('AlertsTable', () => {
  it('alert listesi boşken empty state gösteriyor', () => {
    render(<AlertsTable alerts={[]} />);

    expect(screen.getByText('Aktif alarm yok.')).toBeInTheDocument();
  });

  it('alert varken tabloda doğru sayıda satır render ediyor', () => {
    render(<AlertsTable alerts={sampleAlerts} />);

    // +1 başlık satırı
    expect(screen.getAllByRole('row')).toHaveLength(sampleAlerts.length + 1);
    expect(screen.getByText('client_a')).toBeInTheDocument();
    expect(screen.getByText('client_b')).toBeInTheDocument();
  });

  it('bir satıra tıklanınca onSelectAlert doğru id ile çağrılıyor', async () => {
    const onSelectAlert = vi.fn();
    render(<AlertsTable alerts={sampleAlerts} onSelectAlert={onSelectAlert} />);

    await userEvent.click(screen.getByText('client_b'));

    expect(onSelectAlert).toHaveBeenCalledWith('2');
  });
});
