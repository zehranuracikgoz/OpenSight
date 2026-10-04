import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AlertListItem, CorrelationListItem, LatencySeries } from '../api/types';
import { formatClock, parseApiDate } from '../time';
import { axisProps, COLORS, gridProps, tooltipProps } from './chartTheme';
import styles from './LatencyChart.module.css';
import { fiveMinuteTicks, toChartData, type ChartPoint } from './latencySeries';

interface LatencyChartProps {
  series: LatencySeries | null;
  failed?: boolean;
  alerts: AlertListItem[];
  correlations: CorrelationListItem[];
}

const MINUTE = 60_000;

// alarmın dakikasındaki ortalama gecikme noktasına işaret koyuyor, o dakikada veri yoksa işaret yok
function markerAt(iso: string, byMinute: Map<number, ChartPoint>) {
  const point = byMinute.get(Math.floor(parseApiDate(iso).getTime() / MINUTE) * MINUTE);
  return point && point.latencyMs !== null ? { time: point.time, latencyMs: point.latencyMs } : null;
}

export function LatencyChart({ series, failed = false, alerts, correlations }: LatencyChartProps) {
  const data = series ? toChartData(series) : [];
  const byMinute = new Map(data.map((point) => [point.time, point]));

  // korelasyonun parçası olan performans alarmı baklavayla gösteriliyor, ikinci kez daire çizilmiyor
  const correlatedPerformanceIds = new Set(correlations.map((c) => c.performanceAlertId));
  const performanceMarkers = alerts
    .filter((alert) => alert.type === 'Performans' && !correlatedPerformanceIds.has(alert.alertId))
    .map((alert) => markerAt(alert.createdAt, byMinute))
    .filter((marker) => marker !== null);
  const correlationMarkers = correlations
    .map((c) => markerAt(c.detectedAt, byMinute))
    .filter((marker) => marker !== null);

  let body;
  if (failed && !series) {
    body = <p className={styles.empty}>Gecikme verisi alınamadı - analiz servisi çalışıyor mu?</p>;
  } else if (!series) {
    body = <p className={styles.empty}>Gecikme verisi yükleniyor…</p>;
  } else if (series.request_count === 0) {
    body = <p className={styles.empty}>Son 30 dakikada trafik yok — canlı demoyu başlatın.</p>;
  } else {
    body = (
      <>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data}>
            <CartesianGrid {...gridProps} />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              ticks={fiveMinuteTicks(data)}
              tickFormatter={formatClock}
              padding={{ left: 8, right: 24 }}
              minTickGap={24}
              {...axisProps}
            />
            <YAxis unit="ms" {...axisProps} />
            <Tooltip
              {...tooltipProps}
              labelFormatter={(value) => formatClock(Number(value))}
              formatter={(value) => [`${value} ms`, 'Ortalama gecikme']}
            />
            <Line type="monotone" dataKey="latencyMs" stroke={COLORS.latency} dot={false} strokeWidth={2} connectNulls={false} />
            <Scatter data={performanceMarkers} dataKey="latencyMs" fill={COLORS.performanceAnomaly} shape="circle" />
            <Scatter data={correlationMarkers} dataKey="latencyMs" fill={COLORS.correlation} shape="diamond" />
          </ComposedChart>
        </ResponsiveContainer>
        <p className={styles.note}>
          Dakikalık ortalama gecikme (tüm istemciler). Daire: performans alarmı, baklava: korelasyon.
        </p>
      </>
    );
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Gecikme (son 30 dakika)</h2>
      {body}
    </div>
  );
}
