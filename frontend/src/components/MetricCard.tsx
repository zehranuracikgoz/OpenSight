import styles from './MetricCard.module.css';

interface MetricCardProps {
  label: string;
  value: string | number;
}

// ana dashboard'un üst kısmındaki 4 metrik kartından her biri için
export function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className={styles.card}>
      <span className= {styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </div>
  );
}