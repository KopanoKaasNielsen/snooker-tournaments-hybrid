import { AxiosError } from 'axios';
import api, { apiErrorMessage, setAccessToken } from '@api/client';
const originalAdapter = api.defaults.adapter;
beforeEach(() => { setAccessToken(null); localStorage.clear(); sessionStorage.clear(); });
afterEach(() => { api.defaults.adapter = originalAdapter; });
it('uses a same-origin API prefix, refresh credentials, CSRF header and a timeout', () => {
  expect(api.defaults.baseURL).toBe('/api'); expect(api.defaults.withCredentials).toBe(true);
  expect(api.defaults.timeout).toBe(10000); expect(api.defaults.headers['X-Snooker-Client']).toBe('web');
});
it('explains network errors', () => { expect(apiErrorMessage(new AxiosError('Network Error'))).toMatch(/unable to reach/i); });
it('explains unauthorized and server errors', async () => {
  for (const status of [401, 500]) {
    try {
      await api.get('/health', { adapter: async config => { throw new AxiosError('failed', 'ERR_BAD_RESPONSE', config, undefined, { status, statusText: '', data: {}, headers: {}, config }); } });
      throw new Error('Expected request rejection');
    } catch (error) { expect(apiErrorMessage(error)).toMatch(status === 401 ? /session expired/i : /500/); }
  }
});
it('attaches only in-memory credentials and clears them on logout', async () => {
  const headers: Array<string | undefined> = [];
  api.defaults.adapter = async config => { headers.push(config.headers.get('Authorization') as string | undefined); return { data: {}, status: 200, statusText: 'OK', headers: {}, config }; };
  setAccessToken('memory-only-token'); await api.get('/players/1/balance');
  setAccessToken(null); await api.get('/health');
  expect(headers).toEqual(['Bearer memory-only-token', undefined]);
  expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
});
it('coordinates a single refresh for concurrent expired reads', async () => {
  let refreshes = 0;
  setAccessToken('old');
  api.defaults.adapter = async config => {
    if (config.url === '/auth/refresh') { refreshes += 1; return { data: { access_token: 'new', expires_in: 300 }, status: 200, statusText: 'OK', headers: {}, config }; }
    if (config.headers.get('Authorization') === 'Bearer old') throw new AxiosError('expired', 'ERR_BAD_RESPONSE', config, undefined, { status: 401, statusText: '', data: {}, headers: {}, config });
    return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
  };
  const results = await Promise.all([api.get('/players/1/balance'), api.get('/players/1/transactions')]);
  expect(refreshes).toBe(1); expect(results.every(result => result.status === 200)).toBe(true);
});
it('never automatically retries a failed mutation', async () => {
  const requests: string[] = []; setAccessToken('old');
  api.defaults.adapter = async config => {
    requests.push(config.url ?? '');
    throw new AxiosError('expired', 'ERR_BAD_RESPONSE', config, undefined, { status: 401, statusText: '', data: {}, headers: {}, config });
  };
  await expect(api.post('/tournaments/', {})).rejects.toBeInstanceOf(AxiosError);
  expect(requests).toEqual(['/tournaments/']);
});

it('distinguishes rejected credentials from an expired authenticated session', async () => {
  api.defaults.adapter = async config => { throw new AxiosError('unauthorized', 'ERR_BAD_RESPONSE', config, undefined, { status: 401, statusText: '', data: { detail: 'Invalid username or password' }, headers: {}, config }); };
  try { await api.post('/auth/login', { username: 'unknown', password: 'wrong' }); throw new Error('Expected rejection'); }
  catch (error) { expect(apiErrorMessage(error)).toBe('Invalid username or password.'); }
});
