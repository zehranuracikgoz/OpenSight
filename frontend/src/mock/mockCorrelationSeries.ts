// gerçek bir metrik geçmişi endpoint'i henüz yok - detay panelindeki grafik sahte
// veriyi kullanıyor; gerçek endpoint hazır olunca bu dosya yerine gerçek veri gelecek.
// aynı 30 dakikalık pencerede gecikme ve istek oranı sinyallerinin nasıl örtüştüğünü gösteriyor
export interface CorrelationSeriesPoint {
  timestamp: string;
  latencyMs: number;
  requestRate: number;
}

export function buildMockCorrelationSeries(): CorrelationSeriesPoint[] {
  const points: CorrelationSeriesPoint[] = [];
  const now = Date.now();

  for (let i = 0; i < 30; i++) {
    const timestamp = new Date(now - (30 - i) * 60_000).toISOString();
    // orta noktaya doğru hem gecikme hem istek oranı birlikte tırmanıyor(örtüşen sinyal)
    const spike = i >= 12 && i <= 18 ? (i - 11) * 6 : 0;
    points.push({
      timestamp,
      latencyMs: 45 + spike * 8 + Math.round(Math.sin(i / 3) * 5),
      requestRate: 2 + spike + Math.round(Math.sin(i / 4) * 1),
    });
  }

  return points;
}
