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

// 5 dakikalık yuvarlak etiketler, sırayla ve aralıklı
export function fiveMinuteTicks(data: ChartPoint[]): number[] {
  if (data.length === 0) return [];
  const step = 5 * 60_000;
  const ticks: number[] = [];
  for (let t = Math.ceil(data[0].time / step) * step; t <= data[data.length - 1].time; t += step) ticks.push(t);
  return ticks;
}
