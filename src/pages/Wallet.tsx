const transactions = [
  { id: 'tx-1', description: 'Player payout - Semi Final', amount: -1500 },
  { id: 'tx-2', description: 'Ticket revenue - Session A', amount: 4200 },
  { id: 'tx-3', description: 'Sponsorship bonus', amount: 2500 }
];

const currency = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' });

export default function Wallet() {
  const balance = transactions.reduce((acc, tx) => acc + tx.amount, 0);

  return (
    <section className="page" aria-labelledby="wallet-heading">
      <h2 id="wallet-heading">Tournament wallet</h2>
      <p>Track payouts, sponsorship deals, and real-time ticket revenue.</p>
      <div style={{ marginBottom: '1.5rem' }}>
        <strong>Current balance:</strong> {currency.format(balance)}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">Description</th>
            <th align="right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr key={tx.id}>
              <td style={{ padding: '0.5rem 0' }}>{tx.description}</td>
              <td style={{ padding: '0.5rem 0' }} align="right">
                {currency.format(tx.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
