import styles from './EmptyState.module.css';

// aktif alarm yokken AlertsTable'ın gösterdiği sakin, onaylayıcı durum(ayrı sayfa yok)
export function EmptyState() {
  return (
    <div className={styles.container}>
      <p className={styles.title}>Aktif alarm yok.</p>
      <p className={styles.subtitle}>Sistem izlemeye devam ediyor, her şey normal görünüyor.</p>
    </div>
  );
}