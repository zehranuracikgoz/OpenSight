// backend'in AlertListItemDto'suyla  eşleşiyor
export interface AlertListItem {
  alertId: string;
  clientId: string;
  type: string; // "Performans" | "Davranışsal"
  severity: string; // "Düşük" | "Orta" | "Yüksek"
  createdAt: string;
}

export interface DashboardSummary {
  activeAlertCount: number;
  correlationEventCount: number;
  averageLatencyMs: number;
  activeClientCount: number;
  previousActiveAlertCount: number;
  previousCorrelationEventCount: number;
  previousActiveClientCount: number;
}

// backend'in PagedAlertsDto suyla eşleşiyor
export interface PagedAlerts {
  items: AlertListItem[];
  totalCount: number;
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

// simülatörün (Python, VITE_SIMULATOR_URL) döndürdüğü demo durumu - alanlar snake_case
export interface DemoStatus {
  state: 'bosta' | 'uyaniyor' | 'model_hazirlaniyor' | 'calisiyor' | 'bitti';
  remaining_seconds: number | null;
  duration_seconds: number | null;
  error: string | null;
  scorecard?: DemoScorecard | null;
  scorecard_pending?: boolean;
}

// demo bitince simülatörün hesapladığı karne
export interface DemoScorecard {
  supheli: { total:number; behavioral: number };
  yogun: { total: number; performance: number; behavioral_false: number };
  normal: { total: number; false_alerts: number };
  correlations: { total: number; supheli: number; yogun: number; normal: number };
}

//simülatörün gerçek profil etiketi için
export type ClientProfiles = Record<string, string>;