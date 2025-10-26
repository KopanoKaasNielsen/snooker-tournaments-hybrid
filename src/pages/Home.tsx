import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <section className="page" aria-labelledby="home-heading">
      <h2 id="home-heading">Snooker Tournaments Hybrid</h2>
      <p>
        Manage professional snooker tournaments with real-time insights, player analytics, and
        wallet tracking. Navigate through the dashboard to review live fixtures or head to the wallet
        area to reconcile payouts.
      </p>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <Link to="/dashboard">View dashboard</Link>
        <Link to="/login">Sign in</Link>
      </div>
    </section>
  );
}
