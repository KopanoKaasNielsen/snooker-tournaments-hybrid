import { NavLink, Outlet } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import './AppLayout.css';

export function AppLayout() {
  const { user, logout, notice } = useAuth();
  const navItems = [{ to: '/', label: 'Home' }, ...(user ? [
    { to: '/dashboard', label: 'Dashboard' }, { to: '/wallet', label: 'Wallet' },
    { to: '/profile', label: 'Profile' }, { to: '/settings', label: 'Settings' },
    ...(user.role !== 'player' ? [{ to: '/manage', label: 'Tournament management' }] : []),
    ...(user.role === 'administrator' ? [{ to: '/admin', label: 'Administration' }] : [])
  ] : [{ to: '/login', label: 'Sign in' }, { to: '/register', label: 'Register' }])];
  return <div className="app-layout"><aside className="sidebar"><h1 className="logo">Snooker Hybrid</h1>
    <nav aria-label="Main navigation"><ul>{navItems.map(item => <li key={item.to}>
      <NavLink to={item.to} end={item.to === '/'}>{({ isActive }) => <span className={isActive ? 'active' : undefined}>{item.label}</span>}</NavLink>
    </li>)}</ul></nav>
    {user && <><p>{user.username} · {user.role}</p><button onClick={() => { void logout(); }}>Sign out</button></>}
  </aside><main className="content">{notice && <div role="alert"><p>{notice}</p>
    {notice.includes('Retry sign out') && <button onClick={() => { void logout(); }}>Retry sign out</button>}</div>}<Outlet /></main></div>;
}
export default AppLayout;
