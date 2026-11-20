import axios from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import type { SessionData } from '@/types/user';

declare const __API_BASE_URL__: string;
let accessToken: string | null = null;
let expiresAt = 0;
let refreshFlight: Promise<SessionData> | null = null;
let sessionVersion = 0;
const sessionEndpoint = (url?: string) => /^\/auth\/(login|register|refresh|logout)$/.test(url ?? "");
const api = axios.create({
  baseURL: typeof __API_BASE_URL__ === 'undefined' ? '/api' : __API_BASE_URL__,
  timeout: 10000,
  withCredentials: true,
  headers: { 'X-Snooker-Client': 'web' }
});

export function setAccessToken(token: string | null, expiresIn = 300): void {
  sessionVersion += 1;
  accessToken = token;
  expiresAt = token ? Date.now() + expiresIn * 1000 : 0;
  // Tokens are deliberately never written to browser storage or default headers.
}

export async function prepareLogout(): Promise<void> {
  setAccessToken(null);
  if (refreshFlight) await refreshFlight.catch(() => undefined);
}

export function clearSession(): void {
  setAccessToken(null);
  window.dispatchEvent(new Event('auth:expired'));
}

export function renewSession(): Promise<SessionData> {
  if (!refreshFlight) {
    const version = sessionVersion;
    refreshFlight = api.post<SessionData>('/auth/refresh')
      .then(({ data }) => {
        if (version !== sessionVersion) throw new Error('Session changed while refreshing');
        accessToken = data.access_token; expiresAt = Date.now() + data.expires_in * 1000; return data;
      })
      .catch((error: unknown) => { if (version === sessionVersion) clearSession(); throw error; })
      .finally(() => { refreshFlight = null; });
  }
  return refreshFlight;
}

api.interceptors.request.use(async (config) => {
  const authRequest = sessionEndpoint(config.url);
  if (accessToken && expiresAt - Date.now() < 15000 && !authRequest) await renewSession();
  if (accessToken) config.headers.set('Authorization', `Bearer ${accessToken}`);
  else config.headers.delete('Authorization');
  return config;
});

api.interceptors.response.use(response => response, async (error: unknown) => {
  if (!axios.isAxiosError(error) || error.response?.status !== 401 || !error.config) throw error;
  const config = error.config as InternalAxiosRequestConfig & { authRetried?: boolean };
  if (sessionEndpoint(config.url)) throw error;
  // Recover safe reads only; never automatically replay an application mutation.
  if (!config.authRetried && accessToken && ['get', 'head'].includes(config.method ?? 'get')) {
    config.authRetried = true;
    await renewSession();
    return api.request(config);
  }
  clearSession();
  throw error;
});

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (error.response?.status === 401) return error.config?.url === '/auth/login'
      ? 'Invalid username or password.' : 'Session expired or invalid. Please sign in.';
    if (error.response?.status === 403) {
      if (typeof detail === 'object' && detail !== null && 'code' in detail && detail.code === 'FINANCIAL_OPERATIONS_DISABLED')
        return 'Financial operations are disabled until integrity controls are verified.';
      return 'You do not have permission to perform this operation.';
    }
    if (error.response?.status === 429) return 'Too many attempts. Please wait a minute and try again.';
    if (!error.response) return 'Unable to reach the backend. Check your connection and try again.';
    if (typeof detail === 'string') return detail;
    return `Request failed (${error.response.status}). Please try again.`;
  }
  return 'Unable to load data. Please try again.';
}
export default api;
