import { useEffect, useState } from 'react';
import { getDashboardSummary, getDemoClients, getRecentAlerts } from '../api/client';
import type { AlertListItem, ClientProfiles, DashboardSummary, DemoStatus } from '../api/types';
import { AlertsTable } from '../components/AlertsTable';
import { CorrelationDetailPanel } from '../components/CorrelationDetailPanel';
import { DemoControl } from '../components/DemoControl';
import { DemoScorecard } from '../components/DemoScorecard';
import { LatencyChart } from '../components/LatencyChart';
import { MetricCard, type MetricTrend } from '../components/MetricCard';
import styles from './Dashboard.module.css';

const PAGE_SIZE = 10;
// demo sırasında kartlar ve liste bu aralıkla tazeleniyor
const DEMO_REFRESH_MS = 10000;

const TIME_RANGE_OPTIONS = [
  { label: 'Son 1 Saat', hours: 1 },
  { label: 'Son 24 Saat', hours: 24 },
  { label: 'Son 7 Gün', hours: 168 },
];

// önceki döneme göre artış/azalış yönü ve yüzdesi - önceki dönem 0 ise (sıfıra bölme) yüzde
// hesaplanamıyor, sadece yön gösteriliyor
function computeTrend(current: number, previous: number): MetricTrend {
  if (current === previous) return { direction: 'flat', pct: 0 };
  if (previous=== 0) return { direction: 'up', pct: null };
  return { direction: current > previous ? 'up' : 'down', pct: ((current - previous) / previous) * 100 };
}

// ana dashboard - 4 metrik kartı, gecikme grafiği ve son alarmlar tablosunu bir arada
export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertListItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [timeRangeHours, setTimeRangeHours] =useState(24);
  const [page, setPage] = useState(0) ;
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [clientProfiles, setClientProfiles] = useState<ClientProfiles>({});
  const [refreshTick, setRefreshTick] = useState(0);
  const demoState = demoStatus?.state;
  const scorecardPending = demoStatus?.scorecard_pending;

  // simülatöre ulaşılamazsa rozet çıkmaması için
  useEffect(() => {
    getDemoClients()
      .then(setClientProfiles)
      .catch(() => setClientProfiles({}));
  }, []);

  useEffect(() => {
    if (demoState !== 'calisiyor') return;
    const id = setInterval(() => setRefreshTick((t) => t + 1), DEMO_REFRESH_MS);
    return () => clearInterval(id);
  }, [demoState]);

  // demo bitince ve karne hazır olunca bir kez daha tazeliyor
  useEffect(() => {
    if (demoState === 'bitti') setRefreshTick((t) => t + 1);
  }, [demoState, scorecardPending]);

  useEffect(() => {
    getDashboardSummary(timeRangeHours)
      .then((data) => {
        setSummary(data);
        setError(null);
      })
      .catch(() => setError('Özet veriler alınamadı - backend çalışıyor mu?'));
  }, [timeRangeHours, refreshTick]);

  useEffect(() => {
    getRecentAlerts(PAGE_SIZE, page * PAGE_SIZE, timeRangeHours)
      .then((data) => {
        setAlerts(data.items);
        setTotalCount(data.totalCount);
        setError(null);
      })
      .catch(() => setError('Alarm listesi alınamadı - backend çalışıyor mu?'));
  }, [timeRangeHours, page, refreshTick]);

  function handleTimeRangeChange(hours: number) {
    setTimeRangeHours(hours);
    setPage(0);
  }

  const pageStart = totalCount === 0 ? 0 : page * PAGE_SIZE + 1;
  const pageEnd = Math.min((page + 1) * PAGE_SIZE, totalCount);

  return (
    <div>
      <div className={styles.toolbar}>
        <DemoControl onStatusChange={setDemoStatus} />
        <label className={styles.timeRangeLabel}>
          Zaman Aralığı:{' '}
          <select
            value={timeRangeHours}
            onChange = {(e) => handleTimeRangeChange(Number(e.target.value))}
            className={styles.timeRangeSelect}
          >
            {TIME_RANGE_OPTIONS.map((option) => (
              <option key={option.hours} value={option.hours}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <span className={`${styles.statusPill} ${error ? styles.statusError : styles.statusOk}`}>
          {error ? 'Servislerde sorun var' : 'Tüm servisler aktif'}
        </span>
      </div>

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.metrics}>
        <MetricCard
          label="Aktif Alert"
          value={summary?.activeAlertCount ?? '—'}
          trend={summary ? computeTrend(summary.activeAlertCount, summary.previousActiveAlertCount) : undefined}
        />
        <MetricCard
          label="Korelasyonlu Olay"
          value={summary?.correlationEventCount ?? '—'}
          trend={
            summary ? computeTrend(summary.correlationEventCount, summary.previousCorrelationEventCount) : undefined
          }
        />
        <MetricCard
          label="Ortalama Gecikme"
          value={summary && summary.averageLatencyMs > 0 ? `${summary.averageLatencyMs.toFixed(0)} ms` : '—'}
        />
        <MetricCard
          label="Aktif İstemci"
          value={summary?.activeClientCount ?? '—'}
          trend={summary ? computeTrend(summary.activeClientCount, summary.previousActiveClientCount) : undefined}
        />
      </div>

      {demoState ==='bitti' && (
        <DemoScorecard scorecard={demoStatus?.scorecard} pending={Boolean(scorecardPending)} />
      )}

      <LatencyChart />
      <AlertsTable alerts={alerts} onSelectAlert={setSelectedAlertId} clientProfiles={clientProfiles} />

      {totalCount > 0 && (
        <div className={styles.pagination}>
          <span className={styles.pageInfo}>
            <span className = {styles.pageInfoNumbers}>
              {pageStart}-{pageEnd} / {totalCount}
            </span>{' '}
            gösteriliyor
          </span>
          <div className={styles.pageButtons}>
            <button
              className={styles.pageButton}
              onClick={() => setPage((p) => p - 1)}
              disabled={page === 0}
            >
              Geri
            </button>
            <button
              className={styles.pageButton}
              onClick={() => setPage((p) => p + 1)}
              disabled={pageEnd >= totalCount}
            >
              İleri
            </button>
          </div>
        </div>
      )}

      {selectedAlertId && (
        <CorrelationDetailPanel
          alertId={selectedAlertId}
          onClose={() => setSelectedAlertId(null)}
          clientProfiles={clientProfiles}
        />
      )}
    </div>
  );
}