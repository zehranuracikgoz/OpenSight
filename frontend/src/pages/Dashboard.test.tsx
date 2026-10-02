import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DashboardSummary, DemoStatus } from '../api/types';
import { Dashboard } from './Dashboard';

vi.mock('../api/client', () => ({
  getDashboardSummary: vi.fn(),
  getRecentAlerts: vi.fn(),
  getDemoClients: vi.fn(),
  getDemoStatus: vi.fn(),
  getAlertById: vi.fn(),
  checkApiAwake: vi.fn(),
  startDemo: vi.fn() ,
}));
vi.mock('../components/LatencyChart', () => ({ LatencyChart: () => null }));

import { checkApiAwake, getDashboardSummary, getDemoClients, getDemoStatus, getRecentAlerts } from '../api/client';

const summary: DashboardSummary ={
  activeAlertCount: 1,
  correlationEventCount: 0,
  averageLatencyMs: 0,
  activeClientCount: 1,
  previousActiveAlertCount: 0,
  previousCorrelationEventCount: 0,
  previousActiveClientCount: 0,
};

function demo(overrides: Partial<DemoStatus>): DemoStatus {
  return {state: 'bosta', remaining_seconds: null, duration_seconds: null, error: null, ...overrides };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getDashboardSummary).mockResolvedValue(summary);
  vi.mocked(getRecentAlerts).mockResolvedValue({
    items: [
      { alertId: '1', clientId: 'client_supheli_0000', type: 'Davranışsal', severity: 'Yüksek', createdAt: '2026-01-01T10:00:00Z' },
    ],
    totalCount: 1,
  });
  vi.mocked(getDemoClients).mockResolvedValue({ client_supheli_0000: 'supheli' });
  vi.mocked(getDemoStatus).mockResolvedValue(demo({}));
  vi.mocked(checkApiAwake).mockResolvedValue(true) ;
});

afterEach(() => {
  vi.useRealTimers();
});

describe('Dashboard', () => {
  it('simülatörden gelen profili alarm listesinde rozet olarak gösteriyor', async () => {
    render(<Dashboard />);

    expect (await screen.findByText('şüpheli')).toBeInTheDocument();
  });

  it('simülatöre ulaşılamazsa rozetsiz ama sorunsuz açılıyor', async () => {
    vi.mocked(getDemoClients).mockRejectedValue(new Error('erişilemiyor'));
    render(<Dashboard />);

    expect(await screen.findByText('client_supheli_0000')).toBeInTheDocument();
    expect(screen.queryByText('şüpheli')).not.toBeInTheDocument();
    expect(screen.getByText('Tüm servisler aktif')).toBeInTheDocument();
  });

  it('demo çalışırken metrik kartlarını periyodik tazeliyor', async ()=> {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getDemoStatus).mockResolvedValue(demo({ state: 'calisiyor', remaining_seconds: 200 }));
    render(<Dashboard />);
    await waitFor(() => expect(getDemoStatus).toHaveBeenCalled());
    const before =vi.mocked(getDashboardSummary).mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10500);
    });

    expect(vi.mocked(getDashboardSummary).mock.calls.length).toBeGreaterThan(before);
  });

  it('demo bitince bir kez daha tazeleyip karneyi gösteriyor', async () => {
    vi.mocked(getDemoStatus).mockResolvedValue(
      demo({
        state : 'bitti',
        scorecard: {
          supheli: { total: 3, behavioral: 3 },
          yogun: { total: 3, performance: 3, behavioral_false: 3 },
          normal: { total: 3, false_alerts: 0 },
          correlations: { total: 2, supheli: 2, yogun: 0, normal: 0 },
        },
        scorecard_pending: false,
      }),
    );
    render(<Dashboard />);

    expect(await screen.findByText('Demo Karnesi')).toBeInTheDocument();
    await waitFor(() => expect(vi.mocked(getDashboardSummary).mock.calls.length).toBeGreaterThanOrEqual(2));
  });
  it('demo yokken karne göstermiyor', async () => {
    render(<Dashboard />);

    await screen.findByText('client_supheli_0000');
    expect(screen.queryByText('Demo Karnesi')).not.toBeInTheDocument();
  });

  it('gecikme verisi yokken Ortalama Gecikme kartında 0 ms yerine tire gösteriyor', async () => {
    render(<Dashboard />);

    const label = await screen.findByText('Ortalama Gecikme');
    await waitFor(() =>expect(getDashboardSummary).toHaveBeenCalled());
    expect(label.parentElement).toHaveTextContent('—');
    expect(screen.queryByText('0 ms')).not.toBeInTheDocument();
  });

  it('gecikme verisi varsa ortalamayı ms olarak gösteriyor', async () => {
    vi.mocked(getDashboardSummary).mockResolvedValue({ ...summary, averageLatencyMs: 87.4 });
    render(<Dashboard />);

    expect(await screen.findByText('87 ms')).toBeInTheDocument();
    
  });
});