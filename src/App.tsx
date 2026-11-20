import { Route, Routes } from 'react-router-dom';
import { AuthProvider } from '@/context/AuthContext';
import AppLayout from '@/components/AppLayout';
import ProtectedRoute from '@/components/ProtectedRoute';
import Home from '@/pages/Home';
import Dashboard from '@/pages/Dashboard';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import Wallet from '@/pages/Wallet';
import Profile from '@/pages/Profile';
import Settings from '@/pages/Settings';
import Manage from '@/pages/Manage';
import Admin from '@/pages/Admin';
import NotFound from '@/pages/NotFound';

export default function App() {
  return <AuthProvider><Routes><Route element={<AppLayout />}>
    <Route index element={<Home />} />
    <Route path="login" element={<Login />} />
    <Route path="register" element={<Register />} />
    <Route element={<ProtectedRoute />}>
      <Route path="dashboard" element={<Dashboard />} />
      <Route path="wallet" element={<Wallet />} />
      <Route path="profile" element={<Profile />} />
      <Route path="settings" element={<Settings />} />
    </Route>
    <Route element={<ProtectedRoute roles={['organiser', 'administrator']} />}><Route path="manage" element={<Manage />} /></Route>
    <Route element={<ProtectedRoute roles={['administrator']} />}><Route path="admin" element={<Admin />} /></Route>
    <Route path="*" element={<NotFound />} />
  </Route></Routes></AuthProvider>;
}
