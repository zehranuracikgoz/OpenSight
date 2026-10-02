import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DemoScorecard as Scorecard } from '../api/types';
import { DemoScorecard } from './DemoScorecard';

const scorecard: Scorecard = {
  supheli: { total: 3, behavioral: 3 },
  yogun: { total: 3, performance: 2, behavioral_false: 3 },
  normal: { total: 3, false_alerts: 1 },
  correlations:{ total: 6, supheli: 3, yogun: 2, normal: 1 },
};

describe('DemoScorecard', () => {
  it('karne sayılarını gösteriyor', () => {
    render(<DemoScorecard scorecard={scorecard} pending={false} />);

    expect(screen.getAllByText('3/3')).toHaveLength(2); //şüpheli davranışsal + yoğun yanlış
    expect(screen.getByText('2/3')).toBeInTheDocument();
    expect(screen.getByText(/normal istemciye verilen alarm/)).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
    expect(screen.getByText(/korelasyon: 3 şüpheli, 2 yoğun, 1 normal/)).toBeInTheDocument() ;
  });

  it('yoğun istemcilere verilen davranışsal alarmı yanlış olarak ayrı satırda gösteriyor', () => {
    render(<DemoScorecard scorecard={scorecard} pending={false} />);

    expect(screen.getByText('yoğun istemciye verilen davranışsal alarm (yanlış) ')).toBeInTheDocument();
    expect(screen.getByText('yoğun istemci performans alarmı aldı')).toBeInTheDocument();
  });

  it('karne hazırlanırken bekleme metni gösteriyor' , () => {
    render(<DemoScorecard scorecard={null} pending={true} />);

    expect(screen.getByText('Karne hesaplanıyor…')).toBeInTheDocument();
  });
  it('karne yoksa ve hesaplanmıyorsa hiçbir şey çizmiyor', () => {
    const { container } = render(<DemoScorecard scorecard={null} pending={false} />);

    expect(container).toBeEmptyDOMElement();
  });

});