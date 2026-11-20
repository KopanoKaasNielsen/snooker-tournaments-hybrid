import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import { apiErrorMessage } from '@api/client';

export default function Login() {
  const { login, isLoading } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try {
      await login(String(values.get('username')), String(values.get('password')));
      const from: unknown = location.state?.from;
      navigate(typeof from === 'string' && ['/dashboard', '/wallet', '/profile', '/settings', '/manage', '/admin'].includes(from) ? from : '/dashboard', { replace: true });
    } catch (error) { setError(apiErrorMessage(error)); }
    finally { setBusy(false); }
  };
  return <section className="page"><h2>Sign in</h2>
    <form onSubmit={submit} className="account-form">
      <label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={64} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={128} /></label>
      <button disabled={busy || isLoading}>{busy ? 'Signing in…' : 'Sign in'}</button>
      {error && <p role="alert">{error}</p>}
    </form><p><Link to="/register">Create an account</Link></p>
  </section>;
}
