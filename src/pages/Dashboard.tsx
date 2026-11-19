import { useEffect, useState } from 'react';
import api, { apiErrorMessage } from '@api/client';
interface Tournament { id: number; name: string; date: string | null; status: string; }
export default function Dashboard() {
  const [items, setItems] = useState<Tournament[]>();
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setItems(undefined); setError('');
    api.get<Tournament[]>('/tournaments/', { signal: controller.signal })
      .then(response => { if (!controller.signal.aborted) setItems(response.data); })
      .catch(error => { if (!controller.signal.aborted) setError(apiErrorMessage(error)); });
    return () => controller.abort();
  }, [attempt]);
  return <section className="page"><h2>Operations dashboard</h2>
    {error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(attempt + 1)}>Retry</button></> :
      !items ? <p role="status">Loading tournaments…</p> : items.length === 0 ? <p>No tournaments available.</p> :
      <div>{items.map(item => <article className="card" key={item.id}><h3>{item.name}</h3><p>{item.status}</p><p>{item.date ?? 'Date not set'}</p></article>)}</div>}
  </section>;
}
