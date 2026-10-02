import type { DemoScorecard as Scorecard } from '../api/types';
import styles from './DemoScorecard.module.css';

interface DemoScorecardProps {
  scorecard: Scorecard | null | undefined;
  pending: boolean;
}

// demo sonu mini karne icin
export function DemoScorecard({ scorecard, pending }: DemoScorecardProps) {
  if (!scorecard && !pending) return null ;

  return (
    <section className={styles.card} aria-label="Demo karnesi">
      <h2 className={styles.title}>Demo Karnesi</h2>
      {!scorecard ? (
        <p className={styles.note}>Karne hesaplanıyor…</p>
      ) : (
        <>
          <div className={styles.grid}>
            <div>
              <span className={styles.value}>
                {scorecard.supheli.behavioral}/{scorecard.supheli.total}
              </span>
              <span className={styles.label}>şüpheli istemci davranışsal alarm aldı</span>
            </div>
            <div>
              <span className={styles.value}>
                {scorecard.yogun.performance}/{scorecard.yogun.total}
              </span>
              <span className = {styles.label}>yoğun istemci performans alarmı aldı</span>
            </div>
            <div>
              <span className={styles.value}>
                {scorecard.yogun.behavioral_false}/{scorecard.yogun.total}
              </span>
              <span className={styles.label}>yoğun istemciye verilen davranışsal alarm (yanlış)</span>
            </div>
            <div>
              <span className={styles.value}>{scorecard.normal.false_alerts}</span>
              <span className={styles.label}>normal istemciye verilen alarm (yanlış alarm)</span>
            </div>
            <div>
              <span className={styles.value}>{scorecard.correlations.total}</span>
              <span className={styles.label}>
                korelasyon: {scorecard.correlations.supheli} şüpheli, {scorecard.correlations.yogun} yoğun,{' '}
                {scorecard.correlations.normal} normal
              </span>
            </div>
          </div>

          <p className={styles.note}>
            Sadece bu demonun zaman aralığındaki alarmlar sayıldı; profiller simülatörün gerçek etiketleri. Yoğun
            istemciler meşru kullanıcı, o yüzden onlara verilen davranışsal alarm yanlış pozitif sayılıyor.
          </p>
        </>
      )}
    </section>
  );
  
}