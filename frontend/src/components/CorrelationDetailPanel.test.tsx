import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AlertDetail } from '../api/types';
import { CorrelationDetailPanel } from './CorrelationDetailPanel';

vi.mock('../api/client', () => ({
  getAlertById: vi.fn(),
  acknowledgeAlert: vi.fn(),
  silenceAlert: vi.fn(),
  getLatencyMetrics: vi.fn(),
}));

import { acknowledgeAlert, getAlertById, getLatencyMetrics, silenceAlert } from '../api/client';

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
  vi.mocked(getLatencyMetrics).mockResolvedValue({
    minutes: 30,
    client_id: 'client_a',
    points: [],
    average_latency_ms: null,
    request_count: 0,
  });
});

describe('CorrelationDetailPanel', () => {
  it('yüklenince ham metrikleri ve fallback açıklamayı gösteriyor', async () => {
    render(<CorrelationDetailPanel alertId="alert-1" onClose={() => {}} />);

    expect(await screen.findByText('0.92')).toBeInTheDocument();
    expect(screen.getByText('18.5 req/s')).toBeInTheDocument(); // yüzde değil, req/s
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

  it('çok satırlı açıklamayı satır sonlarıyla gösteriyor', async () => {
    vi.mocked(getAlertById).mockResolvedValue({
      ...sampleDetail,
      description: 'client_a: istek oranı 1.30 req/s.\nKorelasyon: client_a: davranışsal ve performans anomalisi birlikte oluştu.',
    });
    render(<CorrelationDetailPanel alertId="alert-1" onClose= {() => {}} />);

    const description = await screen.findByText(/Korelasyon: client_a: davranışsal ve performans/);
    expect(description.textContent).toContain('\n') ;
    expect(screen.getByText('Neden alarm verdi?')).toBeInTheDocument();
  });

  it('istemciyi ve simülatör profil rozetini gösteriyor', async () => {
    render(<CorrelationDetailPanel alertId="alert-1" onClose={() => {}} clientProfiles={{ client_a: 'supheli' }} />);

    expect(await screen.findByText('client_a')).toBeInTheDocument();
    expect(screen.getByText('şüpheli')).toBeInTheDocument() ;
  });

  it('profil bilgisi yoksa rozetsiz açılıyor', async () => {
    render(<CorrelationDetailPanel alertId="alert-1" onClose={() => {}} />);

    expect(await screen.findByText('client_a')).toBeInTheDocument();
    expect(screen.queryByText('şüpheli')).not.toBeInTheDocument();

  });
});