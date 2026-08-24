import { useEffect, useState } from 'react';
import { getDashboardSummary, getRecentAlerts } from '../api/client';
import type { AlertListItem, DashboardSummary } from '../api/types';
import { AlertsTable } from '../components/AlertsTable';
import { CorrelationDetailPanel } from '../components/CorrelationDetailPanel';
import { LatencyChart } from '../components/LatencyChart';
import { MetricCard } from '../components/MetricCard';
import styles from './Dashboard.module.css';

// ana dashboard - 4 metrik kartı, gecikme grafiği ve son alarmlar tablosunu bir arada
export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  useEffect(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch(() => setError('Özet veriler alınamadı - backend çalışıyor mu?'));

    getRecentAlerts()
      .then(setAlerts)
      .catch(() => setError('Alarm listesi alınamadı - backend çalışıyor mu?'));
  }, []);

  return (
    <div>
      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.metrics}>
        <MetricCard label="Aktif Alert" value={summary?.activeAlertCount ?? '—'} />
        <MetricCard label= "Korelasyonlu Olay" value={summary?.correlationEventCount ?? '—'} />
        <MetricCard
          label="Ortalama Gecikme"
          value={summary ? `${summary.averageLatencyMs.toFixed(0)} ms` : '—'}
        />
        <MetricCard label="Aktif İstemci" value={summary?.activeClientCount ?? '—'} />
      </div>

      <LatencyChart />
      <AlertsTable alerts={alerts} onSelectAlert={setSelectedAlertId} />

      {selectedAlertId && (
        <CorrelationDetailPanel alertId={selectedAlertId} onClose={() => setSelectedAlertId(null)} />
      )}
    </div>
  );
}