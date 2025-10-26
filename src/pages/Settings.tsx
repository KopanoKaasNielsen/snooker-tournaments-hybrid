import { FormEvent, useState } from 'react';
import useAuth from '@/hooks/useAuth';

export default function Settings() {
  const { user } = useAuth();
  const [message, setMessage] = useState('');

  const handlePreferences = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage('Preferences saved. These changes will sync with the backend when connected.');
  };

  return (
    <section className="page" aria-labelledby="settings-heading">
      <h2 id="settings-heading">Settings</h2>
      <p>Control notification preferences and tournament visibility options.</p>
      <form onSubmit={handlePreferences} style={{ display: 'grid', gap: '1rem', maxWidth: '420px' }}>
        <fieldset>
          <legend>Notifications</legend>
          <label>
            <input type="checkbox" name="notifyResults" defaultChecked /> Notify me about match results
          </label>
          <label>
            <input type="checkbox" name="notifyPayments" defaultChecked /> Alert me about wallet updates
          </label>
        </fieldset>
        <fieldset>
          <legend>Availability</legend>
          <label>
            Preferred practice table
            <input type="number" name="practiceTable" min={1} max={8} defaultValue={user?.ranking ?? 1} />
          </label>
        </fieldset>
        <button type="submit">Save preferences</button>
        {message ? (
          <p role="status" style={{ color: '#4ade80' }}>
            {message}
          </p>
        ) : null}
      </form>
    </section>
  );
}
