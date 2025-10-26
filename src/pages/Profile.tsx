import useAuth from '@/hooks/useAuth';

export default function Profile() {
  const { user, isLoading, refreshProfile } = useAuth();

  if (isLoading) {
    return (
      <section className="page" aria-busy="true" aria-labelledby="profile-heading">
        <h2 id="profile-heading">Profile</h2>
        <p>Loading your profile…</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="page" aria-labelledby="profile-heading">
        <h2 id="profile-heading">Profile</h2>
        <p>No profile information available. Please sign in.</p>
        <button type="button" onClick={() => refreshProfile()}>
          Retry
        </button>
      </section>
    );
  }

  return (
    <section className="page" aria-labelledby="profile-heading">
      <h2 id="profile-heading">Welcome back, {user.username}</h2>
      <dl>
        <div>
          <dt>Email</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt>World ranking</dt>
          <dd>{user.ranking}</dd>
        </div>
        <div>
          <dt>Wallet balance</dt>
          <dd>£{user.walletBalance.toLocaleString()}</dd>
        </div>
        {user.favouriteCue ? (
          <div>
            <dt>Favourite cue</dt>
            <dd>{user.favouriteCue}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
