const mockFixtures = [
  { id: 'fixture-1', title: 'Quarter Final - Table 1', status: 'In Progress', table: 1 },
  { id: 'fixture-2', title: 'Quarter Final - Table 2', status: 'Scheduled', table: 2 },
  { id: 'fixture-3', title: 'Quarter Final - Table 3', status: 'Completed', table: 3 }
];

export default function Dashboard() {
  return (
    <section className="page" aria-labelledby="dashboard-heading">
      <h2 id="dashboard-heading">Operations dashboard</h2>
      <p>Monitor fixtures, player availability, and venue readiness in a single view.</p>

      <div role="list" aria-label="Upcoming fixtures" style={{ display: 'grid', gap: '1rem' }}>
        {mockFixtures.map((fixture) => (
          <article key={fixture.id} role="listitem" className="card">
            <h3>{fixture.title}</h3>
            <p>
              Table {fixture.table} · <strong>{fixture.status}</strong>
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
