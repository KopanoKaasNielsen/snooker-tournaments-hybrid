import { NavLink, Outlet } from 'react-router-dom';
import './AppLayout.css';

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/wallet', label: 'Wallet' },
  { to: '/profile', label: 'Profile' },
  { to: '/settings', label: 'Settings' }
];

export function AppLayout() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <h1 className="logo">Snooker Hybrid</h1>
        <nav>
          <ul>
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end={item.to === '/'}>
                  {({ isActive }) => (
                    <span className={isActive ? 'active' : undefined}>{item.label}</span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

export default AppLayout;
