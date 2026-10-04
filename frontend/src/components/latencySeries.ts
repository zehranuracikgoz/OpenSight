import type { LatencySeries } from '../api/types';
import { parseApiDate } from '../time';

export interface ChartPoint {
  time: number;
  latencyMs: number | null;
  requestRate: number;
}

// analiz servisinin dakikalık noktalarını grafik verisine çeviriyor, istek oranı dakikadaki adet / 60 (req/s)
export function toChartData(series: LatencySeries): ChartPoint[] {
  return series.points.map((point) => ({
    time: parseApiDate(point.minute).getTime(),
    latencyMs: point.avg_latency_ms,
    requestRate: Math.round((point.request_count / 60) * 100) / 100,
  }));
}

// kategorik eksende etiketler 5 dakikanın katlarındaki veri noktaları, tooltip bundan etkilenmiyor
export function fiveMinuteTicks(data: ChartPoint[]): number[] {
  return data.filter((point) => new Date(point.time).getMinutes() % 5 === 0).map((point) => point.time);
}
