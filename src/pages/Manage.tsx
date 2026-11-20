import { useState } from 'react';
import type { FormEvent } from 'react';
import api, { apiErrorMessage } from '@api/client';

export default function Manage() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setMessage(''); setError('');
    const values = new FormData(event.currentTarget);
    try {
      await api.post('/tournaments/', { name: String(values.get('name')), type: 'knockout',
        date: new Date(String(values.get('date'))).toISOString(), entry_fee: 0, best_of: 3 });
      setMessage('Tournament created. Your account is assigned to manage it.');
    } catch (error) { setError(apiErrorMessage(error)); }
    finally { setBusy(false); }
  };
  return <section className="page"><h2>Tournament management</h2><p>Only assigned organisers and administrators can change tournament records. Fee collection and payouts remain disabled.</p>
    <form className="account-form" onSubmit={submit}>
      <label>Tournament name<input name="name" required maxLength={100} /></label>
      <label>Date and time<input name="date" type="datetime-local" required /></label>
      <p>Format: knockout · best of 3 · free entry</p>
      <button disabled={busy}>{busy ? 'Creating…' : 'Create tournament'}</button>
    </form>{message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>;
}
