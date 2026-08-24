import type { AlertListItem } from '../api/types';
import styles from './AlertsTable.module.css';
import { EmptyState } from './EmptyState';

interface AlertsTableProps {
  alerts: AlertListItem[];
  onSelectAlert?: (alertId: string) => void;
}

const TYPE_CLASS: Record<string, string> = {
  Performans: styles.typePerformans,
  Davranışsal: styles.typeDavranissal,
  Korelasyonlu: styles.typeKorelasyonlu,
};

const SEVERITY_CLASS: Record<string, string> = {
  Düşük: styles.severityDusuk,
  Orta: styles.severityOrta,
  Yüksek: styles.severityYuksek,
};

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('tr-TR');
}

// son alarmları listeliyor, hiç alarm yoksa EmptyState'e düşecek(ayrı bir sayfa yok, koşullu render
export function AlertsTable({ alerts, onSelectAlert }: AlertsTableProps) {
  if (alerts.length === 0) {
    return <EmptyState />;
  }

  return (
    <table className= {styles.table}>
      <thead>
        <tr>
          <th>İstemci</th>
          <th>Tür</th>
          <th>Şiddet</th>
          <th>Zaman</th>
        </tr>
      </thead>
      <tbody>
        {alerts.map((alert) => (
          <tr
            key={alert.alertId}
            className={onSelectAlert ? styles.clickableRow : undefined}
            onClick={() => onSelectAlert?.(alert.alertId)}
          >
            <td>{alert.clientId}</td>
            <td>
              <span className={`${styles.badge} ${TYPE_CLASS[alert.type] ?? ''}`}>{alert.type}</span>
            </td>
            <td>
              <span className={`${styles.badge} ${SEVERITY_CLASS[alert.severity] ?? ''}`}>
                {alert.severity}
              </span>
            </td>
            <td>{formatTimestamp(alert.createdAt)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

}