import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AlertListItem, CorrelationListItem, LatencySeries } from '../api/types';
import { formatClock, parseApiDate } from '../time';
import { axisProps, COLORS, gridProps, tooltipProps } from './chartTheme';
import styles from './LatencyChart.module.css';
import { fiveMinuteTicks, toChartData } from './latencySeries';

interface LatencyChartProps {
  series: LatencySeries | null;
  failed?: boolean;
  alerts: AlertListItem[];
  correlations: CorrelationListItem[];
}

interface DotProps {
  cx?: number;
  cy?: number;
  value?: number | null;
  index?: number;
}

const MINUTE = 60_000;

function PerformanceDot({ cx, cy, value }: DotProps) {
  if (value == null || cx == null || cy == null) return <g />;
  return <circle cx={cx} cy={cy} r={5} fill={COLORS.performanceAnomaly} />;
}

function CorrelationDot({ cx, cy, value }: DotProps) {
  if (value == null || cx == null || cy == null) return <g />;
  return <path d={`M${cx} ${cy - 7} L${cx + 6} ${cy} L${cx} ${cy + 7} L${cx - 6} ${cy} Z`} fill={COLORS.correlation} />;
}

export function LatencyChart({ series, failed = false, alerts, correlations }: LatencyChartProps) {
  const points = series ? toChartData(series) : [];

  // işaretler aynı veri satırlarında ayrı seri, böylece eksen ve tooltip tek veri kümesinden çalışıyor
  const performanceMinutes = new Set<number>();
  const correlationMinutes = new Set<number>();
  const minuteOf = (iso: string) => Math.floor(parseApiDate(iso).getTime() / MINUTE) * MINUTE;
  // korelasyonun parçası olan performans alarmı baklavayla gösteriliyor, ikinci kez daire çizilmiyor
  const correlatedPerformanceIds = new Set(correlations.map((c) => c.performanceAlertId));
  alerts
    .filter((alert) => alert.type === 'Performans' && !correlatedPerformanceIds.has(alert.alertId))
    .forEach((alert) => performanceMinutes.add(minuteOf(alert.createdAt)));
  correlations.forEach((c) => correlationMinutes.add(minuteOf(c.detectedAt)));

  // o dakikada veri yoksa işaret de yok
  const rows = points.map((point) => ({
    ...point,
    performanceMarker: performanceMinutes.has(point.time) ? point.latencyMs : null,
    correlationMarker: correlationMinutes.has(point.time) ? point.latencyMs : null,
  }));

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
          <ComposedChart data={rows}>
            <CartesianGrid {...gridProps} />
            <XAxis
              dataKey="time"
              ticks={fiveMinuteTicks(points)}
              tickFormatter={formatClock}
              interval={0}
              padding={{ left: 8, right: 16 }}
              {...axisProps}
            />
            <YAxis unit="ms" {...axisProps} />
            <Tooltip
              {...tooltipProps}
              labelFormatter={(value) => formatClock(Number(value))}
              formatter={(value) => [`${value} ms`, 'Ortalama gecikme']}
            />
            <Line type="monotone" dataKey="latencyMs" stroke={COLORS.latency} dot={false} strokeWidth={2} connectNulls={false} />
            <Line
              dataKey="performanceMarker"
              stroke="none"
              dot={(props: DotProps) => <PerformanceDot key={props.index} {...props} />}
              activeDot={false}
              tooltipType="none"
              isAnimationActive={false}
              legendType="none"
            />
            <Line
              dataKey="correlationMarker"
              stroke="none"
              dot={(props: DotProps) => <CorrelationDot key={props.index} {...props} />}
              activeDot={false}
              tooltipType="none"
              isAnimationActive={false}
              legendType="none"
            />
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
