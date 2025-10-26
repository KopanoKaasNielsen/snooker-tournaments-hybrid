import { FormEvent, useState } from 'react';
import api from '@api/client';
import useAuth from '@/hooks/useAuth';

export default function Login() {
  const { refreshProfile, isLoading } = useAuth();
  const [error, setError] = useState<string>();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = formData.get('email');
    const password = formData.get('password');

    if (typeof email !== 'string' || typeof password !== 'string') {
      setError('Please provide both email and password.');
      return;
    }

    try {
      await api.post('/auth/login', { email, password });
      await refreshProfile();
    } catch (err) {
      setError('Unable to sign in with the provided credentials.');
      console.error(err);
    }
  };

  return (
    <section className="page" aria-labelledby="login-heading">
      <h2 id="login-heading">Sign in to continue</h2>
      <p>Access the operations hub and manage live tournament data.</p>
      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '1rem', maxWidth: '400px' }}>
        <label htmlFor="email">
          Email
          <input id="email" name="email" type="email" required />
        </label>
        <label htmlFor="password">
          Password
          <input id="password" name="password" type="password" required />
        </label>
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Signing in…' : 'Sign in'}
        </button>
        {error ? (
          <p role="alert" style={{ color: '#f87171' }}>
            {error}
          </p>
        ) : null}
      </form>
    </section>
  );
}
