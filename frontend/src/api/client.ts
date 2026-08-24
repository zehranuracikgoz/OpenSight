import type { AlertDetail, AlertListItem, DashboardSummary } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

async function getJson<T>(path: string):Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
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