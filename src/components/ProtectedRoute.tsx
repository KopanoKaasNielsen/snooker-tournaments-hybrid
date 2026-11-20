import { Navigate, Outlet, useLocation } from 'react-router-dom';
import useAuth from '@/hooks/useAuth';
import type { Role } from '@/types/user';

export default function ProtectedRoute({ roles }: { roles?: readonly Role[] }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <p role="status">Restoring session…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (roles && !roles.includes(user.role)) return <section className="page"><h2>Access denied</h2><p role="alert">You do not have permission to view this page.</p></section>;
  return <Outlet />;
}
