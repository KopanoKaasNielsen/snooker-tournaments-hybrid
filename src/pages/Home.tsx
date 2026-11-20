import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <section className="page" aria-labelledby="home-heading">
      <h2 id="home-heading">Snooker Tournaments Hybrid</h2>
      <p>
        Sign in to review tournament records and your private player wallet. Financial mutations
        and saved preferences remain unavailable.
      </p>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <Link to="/dashboard">View dashboard</Link>
        <Link to="/login">Sign in</Link>
      </div>
    </section>
  );
}
