import { useEffect, useState } from 'react';
import api, { apiErrorMessage } from '@api/client';
import type { Role, UserProfile } from '@/types/user';

export default function Admin() {
  const [users, setUsers] = useState<UserProfile[]>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    void api.get<UserProfile[]>('/admin/users', { signal: controller.signal })
      .then(({ data }) => { if (!controller.signal.aborted) setUsers(data); })
      .catch(error => { if (!controller.signal.aborted) setError(apiErrorMessage(error)); });
    return () => controller.abort();
  }, [attempt]);
  const changeRole = async (id: number, role: Role) => {
    setBusy(true); setError('');
    try {
      await api.put(`/admin/users/${id}/role`, { role });
      setAttempt(value => value + 1);
    } catch (error) { setError(apiErrorMessage(error)); }
    finally { setBusy(false); }
  };
  return <section className="page"><h2>Administration</h2><p>Role changes revoke that user's sessions. Financial operations remain disabled for administrators too.</p>
    {error && <><p role="alert">{error}</p><button onClick={() => setAttempt(value => value + 1)}>Retry</button></>}
    {!users ? <p role="status">Loading accounts…</p> : <ul>{users.map(user => <li key={user.id}>
      {user.username} · {user.is_active ? 'Active' : 'Inactive'}
      <label>Role for {user.username}<select value={user.role} disabled={busy} onChange={event => { void changeRole(user.id, event.target.value as Role); }}>
        <option value="player">Player</option><option value="organiser">Organiser</option><option value="administrator">Administrator</option>
      </select></label>
    </li>)}</ul>}
  </section>;
}
