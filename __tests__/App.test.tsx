import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '@/App';
import api from '@api/client';
jest.mock('@api/client', () => ({ __esModule: true, default: { get: jest.fn() }, apiErrorMessage: () => 'Unable to reach the backend.' }));
const get = api.get as jest.Mock;
function open(path = '/') {
  return render(<MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></MemoryRouter>);
}
beforeEach(() => get.mockReset());
it('renders Home without unsupported profile requests', () => {
  open();
  expect(screen.getByRole('heading', { name: 'Snooker Tournaments Hybrid' })).toBeInTheDocument();
  expect(get).not.toHaveBeenCalled();
});
it('navigates to settings', () => {
  open(); fireEvent.click(screen.getByRole('link', { name: 'Settings' }));
  expect(screen.getByText(/no settings endpoint/i)).toBeInTheDocument();
});
it('renders the 404 route and home link', () => {
  open('/missing');
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Go to home' }));
  expect(screen.getByRole('heading', { name: 'Snooker Tournaments Hybrid' })).toBeInTheDocument();
});
it('makes no login request or credential form for unsupported authentication', () => {
  open('/login');
  expect(screen.getByRole('heading', { name: 'Sign in unavailable' })).toBeInTheDocument();
  expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  expect(get).not.toHaveBeenCalled();
});
it('shows the profile capability gap', () => {
  open('/profile'); expect(screen.getByText(/no authenticated profile endpoint/i)).toBeInTheDocument();
});
it('loads real tournament records and handles empty results', async () => {
  get.mockResolvedValue({ data: [] }); open('/dashboard');
  expect(screen.getByRole('status')).toHaveTextContent('Loading tournaments');
  expect(await screen.findByText('No tournaments available.')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('/tournaments/', expect.anything());
});

it('displays tournament data returned by the backend', async () => {
  get.mockResolvedValue({ data: [{ id: 7, name: 'Test Cup', date: null, status: 'PENDING' }] });
  open('/dashboard');
  expect(await screen.findByRole('heading', { name: 'Test Cup' })).toBeInTheDocument();
  expect(screen.getByText('PENDING')).toBeInTheDocument();
  expect(screen.getByText('Date not set')).toBeInTheDocument();
});
it('reports dashboard failures and allows retry', async () => {
  get.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: [] });
  open('/dashboard');
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('No tournaments available.')).toBeInTheDocument();
});
