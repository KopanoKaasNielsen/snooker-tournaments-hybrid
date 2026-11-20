import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import { apiErrorMessage } from '@api/client';

export default function Register() {
  const { register } = useAuth();
  const [newPlayer, setNewPlayer] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try {
      await register({ username: String(values.get('username')), password: String(values.get('password')),
        create_player: newPlayer, ...(newPlayer ? { player_name: String(values.get('player_name')) } : {}) });
      navigate('/login', { replace: true });
    } catch (error) { setError(apiErrorMessage(error)); }
    finally { setBusy(false); }
  };
  return <section className="page"><h2>Create account</h2><p>New accounts have the Player role. Existing player records cannot be claimed by name.</p>
    <form onSubmit={submit} className="account-form">
      <label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={64} pattern="[A-Za-z0-9_.-]+" /></label>
      <label>Password (15–128 characters)<input name="password" type="password" autoComplete="new-password" required minLength={15} maxLength={128} /></label>
      <label><input type="checkbox" checked={newPlayer} onChange={event => setNewPlayer(event.target.checked)} />Create a new player profile</label>
      {newPlayer ? <label>New player name<input name="player_name" required maxLength={100} /></label> : <p>Your account will remain unlinked. Existing-player linking requires an approved administrator review process.</p>}
      <button disabled={busy}>{busy ? 'Creating account…' : 'Register'}</button>
      {error && <p role="alert">{error}</p>}
    </form><Link to="/login">Back to sign in</Link>
  </section>;
}
