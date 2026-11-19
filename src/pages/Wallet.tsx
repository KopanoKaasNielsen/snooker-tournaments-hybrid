import { useEffect, useState } from 'react';
import api, { apiErrorMessage } from '@api/client';
interface Player { id: number; name: string; }
interface Balance { player_id: number; balance: number; }
interface Transaction { id: number; type: string; amount: number; timestamp: string; }
export default function Wallet() {
  const [players, setPlayers] = useState<Player[]>();
  const [selected, setSelected] = useState('');
  const [balance, setBalance] = useState<Balance>();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(''); setPlayers(undefined); setBalance(undefined);
    const load = async () => {
      const response = await api.get<Player[]>('/players/', { signal: controller.signal });
      if (controller.signal.aborted) return;
      setPlayers(response.data);
      if (selected) {
        const [b, t] = await Promise.all([
          api.get<Balance>(`/players/${selected}/balance`, { signal: controller.signal }),
          api.get<Transaction[]>(`/players/${selected}/transactions`, { signal: controller.signal })
        ]);
        if (!controller.signal.aborted) { setBalance(b.data); setTransactions(t.data); }
      }
    };
    void load().catch(error => { if (!controller.signal.aborted) setError(apiErrorMessage(error)); });
    return () => controller.abort();
  }, [selected, attempt]);
  return <section className="page"><h2>Player wallet</h2>
    <p>Read-only public player records. Currency is not specified by the backend.</p>
    {error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(attempt + 1)}>Retry</button></> :
      !players ? <p role="status">Loading players…</p> : players.length === 0 ? <p>No players available.</p> :
      <><label>Player <select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Select a player</option>{players.map(player => <option key={player.id} value={player.id}>{player.name}</option>)}</select></label>
        {!selected ? <p>Select a player to view their wallet.</p> : !balance ? <p role="status">Loading wallet…</p> :
          <><p>Current balance: {balance.balance.toFixed(2)}</p>{transactions.length === 0 ? <p>No transactions available.</p> :
            <ul>{transactions.map(tx => <li key={tx.id}>{tx.type}: {tx.amount} · {tx.timestamp}</li>)}</ul>}</>}
      </>}
  </section>;
}
