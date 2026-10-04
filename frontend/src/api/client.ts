import type {
  AlertDetail,
  ClientProfiles,
  CorrelationListItem,
  DashboardSummary,
  DemoStatus,
  LatencySeries,
  PagedAlerts,
  ThresholdSettings,
  UpdateThresholdSettingsPayload,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';
const ANALYSIS_SERVICE_URL = import.meta.env.VITE_ANALYSIS_SERVICE_URL ?? 'http://localhost:8001';
const SIMULATOR_URL = import.meta.env.VITE_SIMULATOR_URL ?? 'http://localhost:10000';

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
    // 403 (salt okunur ortam) ayarlar sayfasında ayırt edilebilsin diye status taşınıyor
    throw Object.assign(new Error(`${path} isteği başarısız oldu: ${response.status}`), { status: response.status });
  }
  return (await response.json()) as T;
}
async function postAction(path: string): Promise<void> {
  const response =await fetch(`${API_BASE_URL}${path}`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`${path} isteği başarısız oldu: ${response.status}`);
  }
}

export function getDashboardSummary(hours = 24): Promise<DashboardSummary> {
  return getJson<DashboardSummary>(`/api/alerts/summary?hours=${hours}`);
}

export function getRecentAlerts(take = 50, skip = 0, hours = 24): Promise<PagedAlerts> {
  return getJson<PagedAlerts>(`/api/alerts?take=${take}&skip=${skip}&hours=${hours}`);
}

export function getCorrelations(): Promise<CorrelationListItem[]> {
  return getJson<CorrelationListItem[]>('/api/alerts/correlations');
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

// Render'da uyuyan servis ilk isteğe ~1 dk'da yanıt verebiliyor, bu yüzden kısa aralıklarla tekrar deniyor
async function fetchWithRetry(url: string, options: RequestInit, retries = 8, delayMs = 4000): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), delayMs);
      try {
        return await fetch(url, { ...options, signal: controller.signal });
      } finally {
        clearTimeout(timeout);
      }
    } catch (err) {
      if (attempt >= retries) throw err;
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
}

export async function checkApiAwake(retries = 15, delayMs = 4000): Promise<boolean> {
  try {
    await fetchWithRetry(`${API_BASE_URL}/health`, {}, retries, delayMs);
    return true;
  } catch {
    return false;
  }
}

export function getDemoStatus(): Promise<DemoStatus> {
  return fetch(`${SIMULATOR_URL}/demo/status`).then((r) => r.json() as Promise<DemoStatus>);
}

export async function getDemoClients(): Promise<ClientProfiles> {
  const response = await fetch(`${SIMULATOR_URL}/demo/clients`);
  if (!response.ok) {
    throw new Error (`/demo/clients isteği başarısız oldu: ${response.status}`);
  }
  return((await response.json()) as { clients: ClientProfiles }).clients;
}

export async function startDemo(durationSeconds?: number): Promise<DemoStatus> {
  const response = await fetchWithRetry(`${SIMULATOR_URL}/demo/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(durationSeconds ? { duration_seconds: durationSeconds } : {}),
  });
  const body = (await response.json()) as DemoStatus & { error?: string };
  if (!response.ok) {
    throw new Error(body.error ?? `demo başlatılamadı: ${response.status}`);
  }
  return body;
}

export function getLatencyMetrics(minutes = 30, clientId?: string): Promise<LatencySeries> {
  const query = clientId ? `?minutes=${minutes}&client_id=${encodeURIComponent(clientId)}` : `?minutes=${minutes}`;
  return getAnalysisJson<LatencySeries>(`/metrics/latency${query}`);
}

export function getThresholdSettings(): Promise<ThresholdSettings> {
  return getAnalysisJson <ThresholdSettings>('/settings/thresholds');
}

export function updateThresholdSettings(
  payload: UpdateThresholdSettingsPayload,
): Promise<ThresholdSettings> {
  return putAnalysisJson<ThresholdSettings>('/settings/thresholds', payload);
}