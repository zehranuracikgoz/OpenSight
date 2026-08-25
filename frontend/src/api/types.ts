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

// backend'in AlertDetailDto'suyla eşleşiyor - detay panelinin ihtiyaç duyduğu tüm alanlar
export interface AlertDetail {
  alertId: string;
  clientId: string;
  type: string;
  severity: string;
  createdAt: string;
  description: string | null;
  zScore: number | null;
  anomalyScore: number | null;
  requestRatePct: number | null;
  relatedEndpoint: string | null;
  acknowledged: boolean;
  silenced: boolean;
  correlationId: string | null;
}

// analiz servisinin (Python/FastAPI) döndürdüğü alan adları snake_case - .NET backend'in
// camelCase'inden farklı, çünkü bu endpoint OpenSight.Api değil analysis-service tarafından sunuluyor
export interface ThresholdSettings {
  z_score_threshold: number;
  contamination:number;
  last_trained_at: string | null;
  alert_counts_last_24h: Record<string, number>;
}

export interface UpdateThresholdSettingsPayload {
  z_score_threshold?: number;
  contamination?:number;
}