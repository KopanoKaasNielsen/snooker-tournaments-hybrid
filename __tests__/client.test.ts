import { AxiosError } from 'axios';
import api, { apiErrorMessage } from '@api/client';
it('defaults to a same-origin API prefix with no credentials and a timeout', () => {
  expect(api.defaults.baseURL).toBe('/api');
  expect(api.defaults.withCredentials).toBe(false);
  expect(api.defaults.timeout).toBe(10000);
});
it('explains network errors', () => {
  expect(apiErrorMessage(new AxiosError('Network Error'))).toMatch(/unable to reach/i);
});
it('explains unauthorized and server errors', async () => {
  for (const status of [401, 500]) {
    try {
      await api.get('/health', { adapter: async config => {
        throw new AxiosError('failed', 'ERR_BAD_RESPONSE', config, undefined, { status, statusText: '', data: {}, headers: {}, config });
      } });
      throw new Error('Expected request rejection');
    } catch (error) {
      expect(apiErrorMessage(error)).toContain(String(status));
    }
  }
});
