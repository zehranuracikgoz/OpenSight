import { useEffect, useState } from 'react';
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
import { acknowledgeAlert, getAlertById, getLatencyMetrics, silenceAlert } from '../api/client';
import type { AlertDetail, ClientProfiles, LatencySeries } from '../api/types';
import { formatClock } from '../time';
import { axisProps, COLORS, gridProps, legendProps, tooltipProps } from './chartTheme';
import styles from './CorrelationDetailPanel.module.css';
import { fiveMinuteTicks, toChartData } from './latencySeries';
import { ProfileBadge } from './ProfileBadge';

interface CorrelationDetailPanelProps {
  alertId: string;
  onClose: () => void;
  clientProfiles?: ClientProfiles;
}

// backend'de açıklama yoksa (Ollama akışı bağlı değil) kural tabanlı şablon metnini burada üretiyor
function fallbackDescription(detail: AlertDetail): string {
  return `${detail.clientId} için ${detail.type} tipinde anomali tespit edildi, şiddet: ${detail.severity}`;
}

function formatMetric(value: number | null, suffix = ''): string {
  return value === null ? '—' : `${value}${suffix}`;
}

// bir alert'e tıklanınca sağdan kayan panel
export function CorrelationDetailPanel({ alertId, onClose, clientProfiles }: CorrelationDetailPanelProps) {
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [error, setError] =useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [silenced, setSilenced] = useState(false);

  // istemcinin son 30 dakikası, analiz servisine ulaşılamazsa null kalıp boş durum gösteriliyor
  const [clientSeries, setClientSeries] = useState<LatencySeries | null>(null);
  const clientId = detail?.clientId;

  useEffect(() => {
    if (!clientId) return;
    setClientSeries(null);
    getLatencyMetrics(30, clientId)
      .then(setClientSeries)
      .catch(() => setClientSeries(null));
  }, [clientId]);

  const chartData = clientSeries ? toChartData(clientSeries) : [];

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
            <p className={styles.client}>
              İstemci: <span className={styles.clientId}>{detail.clientId}</span>
              <ProfileBadge profile={clientProfiles?.[detail.clientId]} />
            </p>
            <div>
              <p className={styles.sectionTitle}>Gecikme + İstek Oranı (son 30 dakika)</p>
              {clientSeries && clientSeries.request_count > 0 ? (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={chartData}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="time"
                    type="number"
                    scale="time"
                    domain={['dataMin', 'dataMax']}
                    ticks={fiveMinuteTicks(chartData)}
                    tickFormatter={formatClock}
                    padding={{ left: 8, right: 16 }}
                    minTickGap={24}
                    {...axisProps}
                  />
                  <YAxis yAxisId="latency" width={40} {...axisProps} />
                  <YAxis yAxisId="rate" orientation="right" width={30} {...axisProps} />
                  <Tooltip {...tooltipProps} labelFormatter={(value) => formatClock(Number(value))} />
                  <Legend {...legendProps} />
                  <Line
                    yAxisId="latency"
                    type="monotone"
                    dataKey ="latencyMs"
                    name="Gecikme (ms)"
                    stroke={COLORS.latency}
                    dot={false}
                    connectNulls={false}
                  />
                  <Line
                    yAxisId="rate"
                    type="monotone"
                    dataKey="requestRate"
                    name="İstek oranı (/sn)"
                    stroke={COLORS.rate}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              ) : (
                <p className={styles.chartNote}>Bu istemci için son 30 dakikada veri yok.</p>
              )}
            </div>

            <div>
              <p className={styles.sectionTitle}>Neden alarm verdi?</p>
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
                  <span className={styles.metricValue}>{formatMetric(detail.requestRatePct, ' req/s')}</span>
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
