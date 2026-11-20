import { useState } from 'react';
import useAuth from '@/hooks/useAuth';

export default function Profile() {
  const { user, isLoading, refreshProfile } = useAuth();
  const [error, setError] = useState('');
  if (isLoading) return <section className="page" aria-busy="true"><h2>Profile</h2><p>Loading your profile…</p></section>;
  if (!user) return <section className="page"><h2>Profile</h2><p>No profile information available.</p>
    <button onClick={() => { void refreshProfile().catch(() => setError('Unable to load your profile.')); }}>Retry</button>{error && <p role="alert">{error}</p>}</section>;
  return <section className="page"><h2>Welcome back, {user.username}</h2><dl>
    <dt>Role</dt><dd>{user.role}</dd>
    <dt>Player record</dt><dd>{user.player_id ?? 'No linked player record'}</dd>
    <dt>Account status</dt><dd>{user.is_active ? 'Active' : 'Inactive'}</dd>
  </dl><p>Wallet details are available on your authenticated wallet page.</p></section>;
}
