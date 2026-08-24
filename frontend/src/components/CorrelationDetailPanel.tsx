import { useEffect, useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { acknowledgeAlert, getAlertById, silenceAlert } from '../api/client';
import type { AlertDetail } from '../api/types';
import { buildMockCorrelationSeries } from '../mock/mockCorrelationSeries';
import styles from './CorrelationDetailPanel.module.css';

interface CorrelationDetailPanelProps {
  alertId: string;
  onClose: () => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

// backend'de açıklama yoksa (Ollama akışı bağlı değil) kural tabanlı şablon metnini burada üretiyor
function fallbackDescription(detail: AlertDetail): string {
  return `${detail.clientId} için ${detail.type} tipinde anomali tespit edildi, şiddet: ${detail.severity}`;
}

function formatMetric(value: number | null, suffix = ''): string {
  return value === null ? '—' : `${value}${suffix}`;
}

// bir alert'e tıklanınca sağdan kayan panel
export function CorrelationDetailPanel({ alertId, onClose }: CorrelationDetailPanelProps) {
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [error, setError] =useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [silenced, setSilenced] = useState(false);

  const series = useMemo(() => buildMockCorrelationSeries(), []);

  useEffect(() => {
    setDetail(null);
    setError(null);
    getAlertById(alertId)
      .then((data) => {
        setDetail(data);
        setAcknowledged(data.acknowledged);
        setSilenced(data.silenced);
      })
      .catch(() => setError('Alarm detayı alınamadı - backend çalışıyor mu?'));
  }, [alertId]);

  async function handleAcknowledge() {
    await acknowledgeAlert(alertId);
    setAcknowledged(true);
  }

  async function handleSilence() {
    await silenceAlert(alertId);
    setSilenced(true);
  }

  return (
    <>
      <div className={styles.overlay} onClick={onClose} />
      <aside className={styles.panel} role="dialog" aria-label="Alarm detayı">
        <header className={styles.header}>
          <h2 className={styles.headerTitle}>Korelasyonlu Olay Detayı</h2>
          <button className={styles.closeButton} onClick={onClose} aria-label="Kapat">
            ×
          </button>
        </header>

        {error && <p className={styles.body}>{error}</p>}

        {detail && (
          <div className={styles.body}>
            <div>
              <p className={styles.sectionTitle}>Gecikme + İstek Oranı (son 30 dakika)</p>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="timestamp" tickFormatter={formatTime} minTickGap={40} />
                  <YAxis yAxisId="latency" width={40} />
                  <YAxis yAxisId="rate" orientation="right" width={30} />
                  <Tooltip labelFormatter={(value) => formatTime(String(value))} />
                  <Legend />
                  <Line
                    yAxisId="latency"
                    type="monotone"
                    dataKey ="latencyMs"
                    name="Gecikme (ms)"
                    stroke="#2563eb"
                    dot={false}
                  />
                  <Line
                    yAxisId="rate"
                    type="monotone"
                    dataKey="requestRate"
                    name="İstek oranı (/sn)"
                    stroke="#f97316"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              <p className={styles.mockNote}>grafik şimdilik örnek (mock) veriyle çiziliyor</p>
            </div>

            <div>
              <p className={styles.sectionTitle}>Açıklama</p>
              <p className={styles.description}>{detail.description ?? fallbackDescription(detail)}</p>
            </div>

            <div>
              <p className={styles.sectionTitle}>Ham Metrikler</p>
              <div className={styles.metrics}>
                <div>
                  <span className={styles.metricLabel}>Z-Score</span>
                  <span className={styles.metricValue}>{formatMetric(detail.zScore)}</span>
                </div>
                <div>
                  <span className={styles.metricLabel}>Anomali Skoru</span>
                  <span className={styles.metricValue}>{formatMetric(detail.anomalyScore)}</span>
                </div>
                <div>
                  <span className={styles.metricLabel}>İstek Oranı</span>
                  <span className={styles.metricValue}>{formatMetric(detail.requestRatePct, '%')}</span>
                </div>
                <div>
                  <span className={styles.metricLabel}>İlişkili Endpoint</span>
                  <span className={styles.metricValue}>{detail.relatedEndpoint ?? '—'}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {detail && (
          <div className={styles.actions}>
            <button
              className={`${styles.actionButton} ${styles.acknowledge}`}
              onClick={handleAcknowledge}
              disabled={acknowledged}
            >
              {acknowledged ? 'Onaylandı' : "Alert'i Onayla"}
            </button>
            <button
              className={`${styles.actionButton} ${styles.silence}`}
              onClick={handleSilence}
              disabled={silenced}
            >
              {silenced ? 'Sessize Alındı' : 'Sessize Al'}
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
