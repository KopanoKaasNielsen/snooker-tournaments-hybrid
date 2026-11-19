import { fireEvent, render, screen } from '@testing-library/react';
import Wallet from '@/pages/Wallet';
import api from '@api/client';
jest.mock('@api/client', () => ({ __esModule: true, default: { get: jest.fn() }, apiErrorMessage: () => 'Unable to reach the backend.' }));
const get = api.get as jest.Mock;
beforeEach(() => get.mockReset());
it('shows loading while requests are pending', () => {
  get.mockReturnValue(new Promise(() => {})); render(<Wallet />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading players');
});
it('shows errors and retries', async () => {
  get.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: [] }); render(<Wallet />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('No players available.')).toBeInTheDocument();
});
it('requires explicit player selection and displays zero balance and empty history', async () => {
  get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/balance') ? { player_id: 1, balance: 0 } : url.endsWith('/transactions') ? [] : [{ id: 1, name: 'Alice' }] }));
  render(<Wallet />);
  fireEvent.change(await screen.findByRole('combobox'), { target: { value: '1' } });
  expect(await screen.findByText('Current balance: 0.00')).toBeInTheDocument();
  expect(screen.getByText('No transactions available.')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('/players/1/balance', expect.anything());
  expect(get).toHaveBeenCalledWith('/players/1/transactions', expect.anything());
});

it('does not present a balance when wallet requests fail', async () => {
  get.mockImplementation((url: string) => url === '/players/' ? Promise.resolve({ data: [{ id: 1, name: 'Alice' }] }) : Promise.reject(new Error('offline')));
  render(<Wallet />);
  fireEvent.change(await screen.findByRole('combobox'), { target: { value: '1' } });
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach');
  expect(screen.queryByText(/Current balance:/)).not.toBeInTheDocument();
});
