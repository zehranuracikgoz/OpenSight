import styles from './MetricCard.module.css';

export interface MetricTrend {
  direction: 'up' | 'down' | 'flat';
  // pct null olabilir - önceki dönem sıfırsa (0'a bölme) yüzde hesaplanamıyor, sadece ok gösteriliyor
  pct: number | null;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  trend?: MetricTrend;
}

const TREND_ARROW: Record<MetricTrend['direction'], string> = {
  up: '▲',
  down: '▼',
  flat: '—',
};

// ana dashboard'un üst kısmındaki 4 metrik kartından her biri için
export function MetricCard({ label, value, trend }: MetricCardProps) {
  return (
    <div className={styles.card}>
      <span className= {styles.label}>{label}</span>
      <div className={styles.valueRow}>
        <span className={styles.value}>{value}</span>
        {trend && (
          <span className={`${styles.trend} ${styles[trend.direction]}`}>
            {TREND_ARROW[trend.direction]}
            {trend.pct !== null && ` ${Math.abs(trend.pct).toFixed(0)}%`}
          </span>
        )}
      </div>
    </div>
  );
}