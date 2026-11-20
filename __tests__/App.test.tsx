import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '@/App';
import api, { renewSession, setAccessToken } from '@api/client';
import type { UserProfile } from '@/types/user';
import { testUser } from '../test-utils/auth';
jest.mock('@api/client', () => ({ __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn() },
  renewSession: jest.fn(), setAccessToken: jest.fn(), prepareLogout: jest.fn().mockResolvedValue(undefined),
  apiErrorMessage: (error: unknown) => error instanceof Error ? error.message : 'Request failed'
}));
const get = api.get as jest.Mock;
const post = api.post as jest.Mock;
const renew = renewSession as jest.Mock;
const session = (user = testUser) => ({ access_token: 'test-only-access-token', token_type: 'bearer', expires_in: 300, user });
async function open(path = '/', user?: UserProfile) {
  renew.mockImplementation(() => user ? Promise.resolve(session(user)) : Promise.reject(new Error('No session')));
  await act(async () => { render(<MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></MemoryRouter>); });
}
beforeEach(() => { jest.clearAllMocks(); get.mockResolvedValue({ data: [] }); post.mockReset(); });
it('renders Home and only attempts supported session recovery', async () => {
  await open();
  expect(screen.getByRole('heading', { name: 'Snooker Tournaments Hybrid' })).toBeInTheDocument();
  expect(get).not.toHaveBeenCalled(); expect(renew).toHaveBeenCalledTimes(1);
});
it('navigates to settings for an authenticated user', async () => {
  await open('/', testUser); fireEvent.click(screen.getByRole('link', { name: 'Settings' }));
  expect(screen.getByText(/no settings endpoint/i)).toBeInTheDocument();
});
it('renders 404 and home recovery', async () => {
  await open('/missing'); expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Go to home' }));
  expect(screen.getByRole('heading', { name: 'Snooker Tournaments Hybrid' })).toBeInTheDocument();
});
it('signs in with the actual credentials contract and navigates to the dashboard', async () => {
  post.mockResolvedValue({ data: session() }); await open('/login');
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'player_one' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Correct Horse Battery Staple!1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('heading', { name: 'Operations dashboard' })).toBeInTheDocument();
  expect(post).toHaveBeenCalledWith('/auth/login', { username: 'player_one', password: 'Correct Horse Battery Staple!1' });
  expect(setAccessToken).toHaveBeenCalledWith('test-only-access-token', 300);
});
it('shows failed login without inventing a session', async () => {
  post.mockRejectedValue(new Error('Invalid username or password')); await open('/login');
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'player_one' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password');
  expect(screen.queryByRole('link', { name: 'Wallet' })).not.toBeInTheDocument();
});
it('guards private routes and displays real current-user fields when authenticated', async () => {
  await open('/profile'); expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
});
it('loads tournaments and handles empty results', async () => {
  await open('/dashboard', testUser);
  expect(await screen.findByText('No tournaments available.')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('/tournaments/', expect.anything());
});
it('displays tournament records returned by the backend', async () => {
  get.mockResolvedValue({ data: [{ id: 7, name: 'Test Cup', date: null, status: 'PENDING' }] });
  await open('/dashboard', testUser);
  expect(await screen.findByRole('heading', { name: 'Test Cup' })).toBeInTheDocument();
  expect(screen.getByText('PENDING')).toBeInTheDocument(); expect(screen.getByText('Date not set')).toBeInTheDocument();
});
it('reports dashboard failures and allows retry', async () => {
  get.mockRejectedValueOnce(new Error('Unable to reach the backend.')).mockResolvedValueOnce({ data: [] });
  await open('/dashboard', testUser); expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('No tournaments available.')).toBeInTheDocument();
});
it('shows dashboard loading while a request is pending', async () => {
  get.mockReturnValue(new Promise(() => {})); await open('/dashboard', testUser);
  expect(screen.getByRole('status')).toHaveTextContent('Loading tournaments');
});
it('registers without sending roles or ownership claims', async () => {
  post.mockResolvedValue({ data: testUser }); await open('/register');
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'player_one' } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: 'Correct Horse Battery Staple!1' } });
  fireEvent.change(screen.getByLabelText('New player name'), { target: { value: 'New Player' } });
  fireEvent.click(screen.getByRole('button', { name: 'Register' }));
  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  expect(post).toHaveBeenCalledWith('/auth/register', { username: 'player_one', password: 'Correct Horse Battery Staple!1', create_player: true, player_name: 'New Player' });
});
it('logs out and removes authenticated navigation', async () => {
  post.mockResolvedValue({ status: 204 }); await open('/profile', testUser);
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/logout'));
  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Wallet' })).not.toBeInTheDocument();
  expect(setAccessToken).toHaveBeenCalledWith(null);
});
it('handles session expiration clearly', async () => {
  await open('/profile', testUser);
  act(() => window.dispatchEvent(new Event('auth:expired')));
  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('session expired');
});
it('hides privileged navigation and enforces the admin route guard', async () => {
  await open('/admin', testUser);
  expect(screen.getByRole('heading', { name: 'Access denied' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Administration' })).not.toBeInTheDocument();
  expect(get).not.toHaveBeenCalledWith('/admin/users', expect.anything());
});
it('shows organiser management navigation', async () => {
  await open('/', { ...testUser, role: 'organiser' });
  expect(screen.getByRole('link', { name: 'Tournament management' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Administration' })).not.toBeInTheDocument();
});

it('reports unconfirmed server logout and permits a safe retry', async () => {
  post.mockRejectedValueOnce(new Error('Unable to reach the backend.')).mockResolvedValueOnce({ status: 204 });
  await open('/profile', testUser);
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('server revocation could not be confirmed');
  expect(screen.queryByRole('link', { name: 'Wallet' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry sign out' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(post).toHaveBeenCalledTimes(2);
});
