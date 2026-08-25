import type {
  AlertDetail,
  AlertListItem,
  DashboardSummary,
  ThresholdSettings,
  UpdateThresholdSettingsPayload,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';
const ANALYSIS_SERVICE_URL = import.meta.env.VITE_ANALYSIS_SERVICE_URL ?? 'http://localhost:8001';

async function getJson<T>(path: string):Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} isteği başarısız oldu: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function getAnalysisJson<T>(path: string):Promise<T> {
  const response = await fetch(`${ANALYSIS_SERVICE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} isteği başarısiz oldu: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function putAnalysisJson<T> (path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${ANALYSIS_SERVICE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${path} isteği başarısız oldu: ${response.status}`);
  }
  return (await response.json()) as T;
}
async function postAction(path: string): Promise<void> {
  const response =await fetch(`${API_BASE_URL}${path}`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`${path} isteği başarısız oldu: ${response.status}`);
  }
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return getJson<DashboardSummary>('/api/alerts/summary');
}

export function getRecentAlerts(take =50): Promise<AlertListItem[]> {
  return getJson<AlertListItem[]>(`/api/alerts?take=${take}`);
}

export function getAlertById(alertId: string): Promise<AlertDetail> {
  return getJson<AlertDetail>(`/api/alerts/${alertId}`);
}

export function acknowledgeAlert(alertId: string): Promise<void> {
  return postAction(`/api/alerts/${alertId}/acknowledge`);
}

export function silenceAlert(alertId: string):Promise<void> {
  return postAction(`/api/alerts/${alertId}/silence`);
}

export function getThresholdSettings(): Promise<ThresholdSettings> {
  return getAnalysisJson <ThresholdSettings>('/settings/thresholds');
}

export function updateThresholdSettings(
  payload: UpdateThresholdSettingsPayload,
): Promise<ThresholdSettings> {
  return putAnalysisJson<ThresholdSettings>('/settings/thresholds', payload);
}