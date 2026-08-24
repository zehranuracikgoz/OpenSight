import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AlertDetail } from '../api/types';
import { CorrelationDetailPanel } from './CorrelationDetailPanel';

vi.mock('../api/client', () => ({
  getAlertById: vi.fn(),
  acknowledgeAlert: vi.fn(),
  silenceAlert: vi.fn(),
}));

import { acknowledgeAlert, getAlertById, silenceAlert } from '../api/client';

const sampleDetail: AlertDetail = {
  alertId: 'alert-1',
  clientId: 'client_a',
  type: 'Davranışsal',
  severity: 'Yüksek',
  createdAt: '2026-01-01T10:00:00Z',
  description: null,
  zScore: null,
  anomalyScore: 0.92,
  requestRatePct: 18.5,
  relatedEndpoint: '/v1/payments',
  acknowledged: false,
  silenced: false,
  correlationId: null,
};

beforeEach(() => {
  vi.mocked(getAlertById).mockResolvedValue(sampleDetail);
  vi.mocked(acknowledgeAlert).mockResolvedValue(undefined);
  vi.mocked(silenceAlert).mockResolvedValue(undefined);
});

describe('CorrelationDetailPanel', () => {
  it('yüklenince ham metrikleri ve fallback açıklamayı gösteriyor', async () => {
    render(<CorrelationDetailPanel alertId="alert-1" onClose={() => {}} />);

    expect(await screen.findByText('0.92')).toBeInTheDocument();
    expect(screen.getByText('18.5%')).toBeInTheDocument();
    expect(screen.getByText('/v1/payments')).toBeInTheDocument();
    // description null olduğu için fallback şablon üretiliyor
    expect(
      screen.getByText('client_a için Davranışsal tipinde anomali tespit edildi, şiddet: Yüksek'),
    ).toBeInTheDocument();
  });

  it('kapatma butonu onClose çağırıyor', async () => {
    const onClose = vi.fn();
    render(<CorrelationDetailPanel alertId="alert-1" onClose={onClose} />);
    await screen.findByText('0.92');

    await userEvent.click(screen.getByLabelText('Kapat'));

    expect(onClose).toHaveBeenCalledOnce();
  });

  it('onayla butonu backend çağrısı yapıp durumu güncelliyor', async () => {
    render(<CorrelationDetailPanel alertId= "alert-1" onClose={() => {}} />);
    await screen.findByText('0.92');

    await userEvent.click(screen.getByRole('button', { name: "Alert'i Onayla" }));

    expect(acknowledgeAlert).toHaveBeenCalledWith('alert-1');
    expect(await screen.findByRole('button', { name: 'Onaylandı' })).toBeDisabled();
  });
});
