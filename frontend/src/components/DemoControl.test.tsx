import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { DemoStatus } from '../api/types';
import { DemoControl } from './DemoControl';

vi.mock('../api/client', () => ({
  checkApiAwake: vi.fn(),
  getDemoStatus: vi.fn(),
  startDemo: vi.fn(),
}));

import { checkApiAwake, getDemoStatus, startDemo } from '../api/client';

function status(overrides: Partial<DemoStatus>): DemoStatus {
  return { state: 'bosta', remaining_seconds: null, duration_seconds: null, error: null, ...overrides };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(checkApiAwake).mockResolvedValue(true);
  vi.mocked(getDemoStatus).mockResolvedValue(status({}));
});

describe('DemoControl', () => {
  it('boşta durumunda başlat butonunu gösteriyor', async () => {
    render(<DemoControl />);

    expect(await screen.findByRole('button', { name: 'Canlı Demoyu Başlat' })).toBeInTheDocument();
  });

  it('API uyuyorsa uyanıyor rozetini gösteriyor', async () => {
    vi.mocked(checkApiAwake).mockResolvedValue(false);
    render(<DemoControl />);

    expect(await screen.findByText('Sistem uyanıyor (~1 dk)…')).toBeInTheDocument();
  });

  it('butona basınca startDemo çağırıyor ve durumu güncelliyor', async () => {
    let resolveStatus: (value: DemoStatus) => void = () => {};
    vi.mocked(getDemoStatus).mockReturnValue(new Promise((resolve) => (resolveStatus = resolve)));
    vi.mocked(startDemo).mockResolvedValue(status({ state: 'uyaniyor' }));
    render(<DemoControl />);
    const button = await screen.findByRole('button', { name: 'Canlı Demoyu Başlat' });

    await userEvent.click(button);

    expect(startDemo).toHaveBeenCalled();
    expect(await screen.findByText('Sistem uyanıyor (~1 dk)…')).toBeInTheDocument();
    resolveStatus(status({}));
  });

  it('çalışıyor durumunda kalan süreyi gösteriyor', async () => {
    vi.mocked(getDemoStatus).mockResolvedValue(status({ state: 'calisiyor', remaining_seconds: 125 }));
    render(<DemoControl />);

    expect(await screen.findByText(/kalan süre: 2:05/)).toBeInTheDocument();
  });

  it('kota hatasını gösteriyor ve butonu tekrar sunuyor', async () => {
    vi.mocked(startDemo).mockRejectedValue(new Error('bugünkü demo sınırına (3) ulaşıldı'));
    render(<DemoControl />);
    const button = await screen.findByRole('button', { name: 'Canlı Demoyu Başlat' });

    await userEvent.click(button);

    expect(await screen.findByText('bugünkü demo sınırına (3) ulaşıldı')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Canlı Demoyu Başlat' })).toBeInTheDocument();
  });

  it('bitti durumunda tekrar başlatma butonunu sunuyor', async () => {
    vi.mocked(getDemoStatus).mockResolvedValue(status({ state: 'bitti' }));
    render(<DemoControl />);

    expect(await screen.findByText('Demo tamamlandı')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Canlı Demoyu Başlat' })).toBeInTheDocument();
  });

  it('boşta/bitti durumunda tekrar yoklama yapmıyor', async () => {
    render(<DemoControl />);
    await screen.findByRole('button', { name: 'Canlı Demoyu Başlat' });

    await new Promise((resolve) => setTimeout(resolve, 50));

    await waitFor(() => expect(vi.mocked(getDemoStatus)).toHaveBeenCalledTimes(1));
  });
});
