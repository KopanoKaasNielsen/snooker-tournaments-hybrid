import { useEffect, useState } from 'react';
import api, { apiErrorMessage } from '@api/client';
import useAuth from '@/hooks/useAuth';
interface Balance { player_id: number; balance: number; }
interface Transaction { id: number; type: string; amount: number; timestamp: string; }
export default function Wallet() {
  const { user } = useAuth();
  const playerId = user?.player_id;
  const [balance, setBalance] = useState<Balance>();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!playerId) return;
    const controller = new AbortController();
    setError(''); setBalance(undefined); setTransactions([]);
    void Promise.all([
      api.get<Balance>(`/players/${playerId}/balance`, { signal: controller.signal }),
      api.get<Transaction[]>(`/players/${playerId}/transactions`, { signal: controller.signal })
    ]).then(([b, t]) => { if (!controller.signal.aborted) { setBalance(b.data); setTransactions(t.data); } })
      .catch(error => { if (!controller.signal.aborted) setError(apiErrorMessage(error)); });
    return () => controller.abort();
  }, [playerId, attempt]);
  return <section className="page"><h2>Player wallet</h2><p>Private read-only records. Currency is not specified by the backend.</p>
    <p>Deposits, withdrawals and fee payments are disabled until financial integrity controls are verified.</p>
    {!playerId ? <p>No linked player record. Contact an administrator about the ownership review process.</p> :
      error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(attempt + 1)}>Retry</button></> :
      !balance ? <p role="status">Loading wallet…</p> : <><p>Current balance: {balance.balance.toFixed(2)}</p>
        {transactions.length === 0 ? <p>No transactions available.</p> : <ul>{transactions.map(tx => <li key={tx.id}>{tx.type}: {tx.amount} · {tx.timestamp}</li>)}</ul>}</>}
  </section>;
}
