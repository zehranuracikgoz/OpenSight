import styles from './ZScoreDistributionChart.module.css';

interface ZScoreDistributionChartProps {
  threshold: number;
}

const WIDTH = 400;
const HEIGHT = 100;
const Z_AXIS_MAX = 7;

// iki egriyi de sabit bir Gauss formulüyle ciziyor - gercek trafikten olculmus bir z-score
// dagilimi degil, sadece "normal" ve "anomali" dagilimlarinin nasil ayrisabildigini gosteren
// temsili bir illustrasyon
function buildBellCurvePath(mean: number, std: number, amplitude: number): string {
  const steps = 60;
  const points: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * WIDTH;
    const z = (x / WIDTH) * Z_AXIS_MAX;
    const y = HEIGHT - amplitude * Math.exp(-((z - mean) ** 2) / (2 * std * std));
    points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return  `M ${points.join(' L ')}`;
}

// ayarlar sayfasindaki z-score slider'inin ustunde, mevcut esigin normal/anomali
// dagilimlarina gore nerede durdugunu gosteren illustratif grafik
export function ZScoreDistributionChart({ threshold }: ZScoreDistributionChartProps) {
  const normalPath = buildBellCurvePath(1.0, 1.1, HEIGHT * 0.85);
  const anomalyPath = buildBellCurvePath(4.8, 1.4, HEIGHT * 0.55);
  const thresholdX = (threshold / Z_AXIS_MAX) * WIDTH;

  return (
    <div className= {styles.container}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className={styles.svg} preserveAspectRatio="none">
        <path d={normalPath} className={styles.normalCurve} />
        <path d={anomalyPath} className={styles.anomalyCurve} />
        <line x1={thresholdX} y1={0} x2={thresholdX} y2={HEIGHT} className={styles.thresholdLine} />
      </svg>
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.normalDot} /> normal trafik
        </span>
        <span className={styles.legendItem}>
          <span className={styles.anomalyDot} /> anomali
        </span>
      </div>
      <p className={styles.illustrativeNote}>bu grafik gerçek z-score dağılımından değil, temsili bir eğriden çiziliyor</p>
    </div>
  );
}