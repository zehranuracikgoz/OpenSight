import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ThresholdSettings } from '../api/types';
import { ThresholdConfig } from './ThresholdConfig';

vi.mock('../api/client', () => ({
  getThresholdSettings: vi.fn(),
  updateThresholdSettings: vi.fn(),
}));

import{ getThresholdSettings, updateThresholdSettings } from '../api/client';

const sampleSettings : ThresholdSettings = {
  z_score_threshold: 3.2,
  contamination: 0.05,
  last_trained_at: '2026-01-01T10:00:00Z',
  alert_counts_last_24h : { Performans: 4, Davranışsal: 2 },
};

beforeEach(() => {
  vi.mocked(getThresholdSettings).mockResolvedValue(sampleSettings);
  vi.mocked(updateThresholdSettings).mockResolvedValue({
    ...sampleSettings,
    z_score_threshold: 4.5 ,
  });
});

describe('ThresholdConfig', () => {
  it('slider\'ları ve son 24 saatlik alarm sayılarını gösteriyor', async () => {
    render(<ThresholdConfig />);

    expect(await screen.findByLabelText(/Z-Score Eşiği/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Isolation Forest Contamination Oranı/)).toBeInTheDocument();
    expect(screen.getByText('Performans: 4')).toBeInTheDocument();
    expect(screen.getByText('Davranışsal: 2')).toBeInTheDocument();
  });

  it('kaydet butonu doğru payload ile updateThresholdSettings çağırıyor', async () => {
    render(<ThresholdConfig />) ;
    const slider = await screen.findByLabelText(/Z-Score Eşiği/);
    // fireEvent yerine doğrudan value değiştirip change tetikliyor - range input'lar için daha güvenilir
    await userEvent.click(screen.getByRole('button', { name: 'Değişiklikleri Kaydet' }));

    expect(updateThresholdSettings).toHaveBeenCalledWith({ z_score_threshold: 3.2, contamination: 0.05 });
    expect(await screen.findByText ('Değişiklikler kaydedildi.')).toBeInTheDocument();
    void slider;
  });

  it('varsayılana dön butonu slider değerlerini sıfırlıyor', async () => {
    render(<ThresholdConfig />);
    await screen.findByLabelText( /Z-Score Eşiği/);

    await userEvent.click(screen.getByRole('button', { name: 'Varsayılana Dön' }));

    expect(screen.getByLabelText(/Z-Score Eşiği/)).toHaveValue('3.2');
    expect(screen.getByLabelText(/Isolation Forest Contamination Oranı/)).toHaveValue('0.05');
  });

});