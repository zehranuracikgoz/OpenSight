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

// turuncu nokta = performans anomalisi, amber diamond = korelasyonlu olay(mock veri
export function LatencyChart() {
  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Gecikme (son 30 dakika)</h2>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data = {mockLatencyData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="timestamp" tickFormatter={formatTime} minTickGap={30} />
          <YAxis unit="ms" />
          <Tooltip
            labelFormatter={(value) => formatTime(String(value))}
            formatter={(value) => [`${value} ms`, 'Gecikme']}
          />
          <Line type="monotone" dataKey="latencyMs" stroke ="#2563eb" dot={false} strokeWidth={2} />
          <Scatter data={performanceAnomalyPoints} dataKey="latencyMs" fill="#f97316" shape="circle" />
          <Scatter data= {correlatedPoints} dataKey="latencyMs" fill="#f59e0b" shape="diamond" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}