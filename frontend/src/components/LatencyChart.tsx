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
import { mockLatencyData } from '../mock/mockLatencyData';
import { axisProps, COLORS, gridProps, tooltipProps } from './chartTheme';
import styles from './LatencyChart.module.css';

function formatTime(iso: string) : string {
  return new Date(iso).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

const performanceAnomalyPoints = mockLatencyData
  .filter((point) => point.isPerformanceAnomaly && !point.isCorrelated)
  .map((point) => ({ timestamp: point.timestamp, latencyMs: point.latencyMs }));

const correlatedPoints =mockLatencyData
  .filter((point) => point.isCorrelated)
  .map((point) => ({ timestamp: point.timestamp, latencyMs: point.latencyMs }));

export function LatencyChart() {
  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Gecikme (son 30 dakika)</h2>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data = {mockLatencyData}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="timestamp" tickFormatter={formatTime} minTickGap={30} {...axisProps} />
          <YAxis unit="ms" {...axisProps} />
          <Tooltip
            {...tooltipProps}
            labelFormatter={(value) => formatTime(String(value))}
            formatter={(value) => [`${value} ms`, 'Gecikme']}
          />
          <Line type="monotone" dataKey="latencyMs" stroke={COLORS.latency} dot={false} strokeWidth={2} />
          <Scatter data={performanceAnomalyPoints} dataKey="latencyMs" fill={COLORS.performanceAnomaly} shape="circle" />
          <Scatter data={correlatedPoints} dataKey="latencyMs" fill={COLORS.correlation} shape="diamond" />
        </ComposedChart>
      </ResponsiveContainer>
      <p className={styles.mockNote}>grafik şimdilik örnek (mock) veriyle çiziliyor</p>
    </div>
  );
}