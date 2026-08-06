import type { AlertListItem, DashboardSummary } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

async function getJson<T>(path: string):Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} isteği başarısız oldu: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return getJson<DashboardSummary>('/api/alerts/summary');
}

export function getRecentAlerts(take =50): Promise<AlertListItem[]> {
  return getJson<AlertListItem[]>(`/api/alerts?take=${take}`);
}
