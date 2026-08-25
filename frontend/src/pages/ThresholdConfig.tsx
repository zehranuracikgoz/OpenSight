import { useEffect, useState } from 'react';
import { getThresholdSettings, updateThresholdSettings } from '../api/client';
import type { ThresholdSettings } from '../api/types';
import styles from './ThresholdConfig.module.css';

const DEFAULT_Z_SCORE_THRESHOLD = 3.2;
const DEFAULT_CONTAMINATION = 0.05;

function formatDateTime(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString('tr-TR') : 'henüz eğitilmedi';
}

// operasyon ekibinin z-score eşiğini ve isolation forest contamination oranını ayarladığı ekran
export function ThresholdConfig() {
  const [settings, setSettings] = useState<ThresholdSettings | null>(null);
  const [zScoreThreshold, setZScoreThreshold] = useState(DEFAULT_Z_SCORE_THRESHOLD);
  const [contamination, setContamination] = useState(DEFAULT_CONTAMINATION);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    getThresholdSettings()
      .then((data) => {
        setSettings(data);
        setZScoreThreshold(data.z_score_threshold);
        setContamination(data.contamination);
      })
      .catch(() => setError( 'Ayarlar alınamadı - analiz servisi çalışıyor mu?'));
  }, []);

  async function handleSave() {
    setError(null);
    setSavedMessage(null);
    try {
      const updated = await updateThresholdSettings({
        z_score_threshold:zScoreThreshold,
        contamination: contamination,
      });
      setSettings(updated);
      setSavedMessage('Değişiklikler kaydedildi.');
    } catch {
      setError ('Ayarlar kaydedilemedi - analiz servisi çalışıyor mu?');
    }
  }

  function handleReset() {
    setZScoreThreshold(DEFAULT_Z_SCORE_THRESHOLD);
    setContamination(DEFAULT_CONTAMINATION);
    setSavedMessage (null);
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Eşik Değerleri Yapılandırma</h2>

      {error && <p className={styles.error}>{error}</p>}
      {savedMessage && <p className={styles.saved}>{savedMessage}</p>}

      <div className={styles.field}>
        <label htmlFor="zScoreThreshold">Z-Score Eşiği: {zScoreThreshold.toFixed(1)}</label>
        <input
          id = "zScoreThreshold"
          type="range"
          min={1}
          max={6}
          step={0.1}
          value={zScoreThreshold}
          onChange={(e) => setZScoreThreshold(Number(e.target.value))}
        />
        <p className={styles.hint}>
          Performans anomalisi için gecikmenin ortalamadan kaç standart sapma uzaklaşınca alarm
          üretileceğini belirliyor. Düşük değer daha hassas, yüksek değer daha az yanlış alarm demek.
        </p>
      </div>

      <div className={styles.field}>
        <label htmlFor="contamination">
          Isolation Forest Contamination Oranı: {contamination.toFixed(2)}
        </label>
        <input
          id="contamination"
          type="range"
          min = {0.01}
          max = {0.5}
          step={0.01}
          value={contamination}
          onChange={(e) => setContamination(Number(e.target.value))}
        />
        <p className={styles.hint}>
          Davranışsal anomali tespitinde trafiğin ne kadarının "anormal" kabul edileceğinin oranı.
          Yüksek değer daha fazla istemciyi şüpheli işaretliyor.
        </p>
        <p className={styles.hint}>
          Bu değişiklik modelin bir sonraki yeniden eğitiminde etkili olur, mevcut modeli anlık
          olarak değiştirmez.
        </p>
      </div>

      <div className={styles.info}>
        <p className={styles.sectionTitle}>Son 24 Saatte Üretilen Alarmlar</p>
        <p>Performans: {settings?.alert_counts_last_24h.Performans ?? '—'}</p>
        <p>Davranışsal: {settings?.alert_counts_last_24h['Davranışsal'] ?? '—'}</p>
        <p className={styles.sectionTitle}>Modelin Son Eğitim Zamanı</p>
        <p>{formatDateTime(settings?.last_trained_at)}</p>
      </div>

      <div className={styles.actions}>
        <button className={styles.saveButton} onClick={handleSave}>
          Değişiklikleri Kaydet
        </button>
        <button className={styles.resetButton} onClick={handleReset}>
          Varsayılana Dön
          
        </button>
      </div>
    </div>
  );
}