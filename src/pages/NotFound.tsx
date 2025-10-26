import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <section className="page" aria-labelledby="not-found-heading">
      <h2 id="not-found-heading">Page not found</h2>
      <p>The page you are looking for does not exist. Return to the dashboard to continue.</p>
      <Link to="/">Go to home</Link>
    </section>
  );
}
