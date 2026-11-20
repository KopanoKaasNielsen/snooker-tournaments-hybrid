import { fireEvent, screen } from '@testing-library/react';
import Wallet from '@/pages/Wallet';
import api from '@api/client';
import { renderWithAuth } from '../test-utils/auth';
jest.mock('@api/client', () => ({ __esModule: true, default: { get: jest.fn() }, apiErrorMessage: () => 'Unable to reach the backend.' }));
const get = api.get as jest.Mock;
beforeEach(() => get.mockReset());
function successful(url: string) { return Promise.resolve({ data: url.endsWith('/balance') ? { player_id: 1, balance: 0 } : [] }); }
it('shows loading while wallet requests are pending', () => {
  get.mockReturnValue(new Promise(() => {})); renderWithAuth(<Wallet />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading wallet');
});
it('shows errors and retries', async () => {
  let failure = true;
  get.mockImplementation((url: string) => failure ? Promise.reject(new Error('offline')) : successful(url));
  renderWithAuth(<Wallet />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach');
  failure = false;
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Current balance: 0.00')).toBeInTheDocument();
});
it('reads only the server-linked player and displays zero balance and empty history', async () => {
  get.mockImplementation(successful); renderWithAuth(<Wallet />);
  expect(await screen.findByText('Current balance: 0.00')).toBeInTheDocument();
  expect(screen.getByText('No transactions available.')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('/players/1/balance', expect.anything());
  expect(get).toHaveBeenCalledWith('/players/1/transactions', expect.anything());
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /deposit|withdraw/i })).not.toBeInTheDocument();
});
it('does not present a balance when wallet requests fail', async () => {
  get.mockRejectedValue(new Error('offline')); renderWithAuth(<Wallet />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach');
  expect(screen.queryByText(/Current balance:/)).not.toBeInTheDocument();
});
it('does not fabricate a zero wallet for an unlinked account', () => {
  renderWithAuth(<Wallet />, { user: { id: 2, username: 'Unlinked', role: 'player', player_id: null, is_active: true } });
  expect(screen.getByText(/No linked player record/)).toBeInTheDocument();
  expect(get).not.toHaveBeenCalled();
  expect(screen.queryByText(/Current balance:/)).not.toBeInTheDocument();
});
