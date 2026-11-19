import axios from 'axios';

declare const __API_BASE_URL__: string;
const api = axios.create({
  baseURL: typeof __API_BASE_URL__ === 'undefined' ? '/api' : __API_BASE_URL__,
  timeout: 10000,
  withCredentials: false
});

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) return 'Access denied (401). The backend does not provide sign-in.';
    if (!error.response) return 'Unable to reach the backend. Check your connection and try again.';
    return `Request failed (${error.response.status}). Please try again.`;
  }
  return 'Unable to load data. Please try again.';
}

export default api;
