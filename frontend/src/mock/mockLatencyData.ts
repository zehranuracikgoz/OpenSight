// gerçek bir gecikme metrik endpoint'i henüz yok - bu dosya sahte veri üretmek icin,
// gerçek endpoint olunca bu dosya yerine gerçek veriyi kullanılacak
export interface LatencyPoint {
  timestamp: string;
  latencyMs:number;
  isPerformanceAnomaly?: boolean;
  isCorrelated?: boolean;
}

function buildMockLatencyData(): LatencyPoint[] {
  const points: LatencyPoint[] = [];
  const now = Date.now();

  for (let i = 0; i < 30; i++) {
    const timestamp = new Date(now - (30 - i) * 60_000).toISOString();
    const baseLatency = 40 + Math.round(Math.sin(i / 3) * 8);
    points.push({ timestamp, latencyMs: baseLatency });
  }

  // performans anomalisi örneği
  points[10] = { ...points[10], latencyMs: 320, isPerformanceAnomaly: true };
  // aynı anda davranışsal anomaliyle çakışıp korelasyonlu olaya dönüşen örnek
  points[20] = { ...points[20], latencyMs: 280, isPerformanceAnomaly: true, isCorrelated: true };

  return points;
}
export const mockLatencyData: LatencyPoint[] = buildMockLatencyData();