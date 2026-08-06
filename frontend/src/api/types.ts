// backend'in AlertListItemDto'suyla  eşleşiyor
export interface AlertListItem {
  alertId: string;
  clientId: string;
  type: string; // "Performans" | "Davranışsal"
  severity: string; // "Düşük" | "Orta" | "Yüksek"
  createdAt: string;
}

// backend'in DashboardSummaryDto'suyla eşleşiyor
export interface DashboardSummary {
  activeAlertCount: number;
  correlationEventCount: number;
  averageLatencyMs: number;
  activeClientCount: number;
}