import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <section className="page" aria-labelledby="home-heading">
      <h2 id="home-heading">Snooker Tournaments Hybrid</h2>
      <p>
        Review tournament records and player wallet balances from the backend. Account sign-in
        and saved preferences are not currently available.
      </p>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <Link to="/dashboard">View dashboard</Link>
        <Link to="/login">Sign in</Link>
      </div>
    </section>
  );
}
