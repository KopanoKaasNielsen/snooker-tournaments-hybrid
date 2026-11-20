import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import api, { apiErrorMessage, renewSession, setAccessToken, prepareLogout } from '@api/client';
import type { SessionData, UserProfile } from '@/types/user';

export interface Registration { username: string; password: string; create_player: boolean; player_name?: string; }
export interface AuthContextValue {
  isLoading: boolean;
  user?: UserProfile;
  notice?: string;
  refreshProfile: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  register: (input: Registration) => Promise<void>;
  logout: () => Promise<void>;
}
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { readonly children: ReactNode }) {
  const [user, setUser] = useState<UserProfile>();
  const [isLoading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string>();
  const current = useRef<UserProfile>();
  const operation = useRef(0);
  current.current = user;
  useEffect(() => {
    let active = true;
    const expired = () => {
      if (current.current) setNotice('Your session expired. Please sign in again.');
      setUser(undefined);
    };
    window.addEventListener('auth:expired', expired);
    void renewSession().then(data => { if (active) setUser(data.user); })
      .catch(() => { if (active) setUser(undefined); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; window.removeEventListener('auth:expired', expired); };
  }, []);

  useEffect(() => {
    if (!user) return;
    const timer = window.setInterval(() => {
      const version = operation.current;
      void renewSession().then(data => { if (version === operation.current) setUser(data.user); })
        .catch(() => { if (version === operation.current) setUser(undefined); });
    }, 270000);
    return () => window.clearInterval(timer);
  }, [user?.id]);

  const refreshProfile = useCallback(async () => {
    const response = await api.get<UserProfile>('/auth/me');
    setUser(response.data);
  }, []);
  const login = async (username: string, password: string) => {
    const { data } = await api.post<SessionData>('/auth/login', { username, password });
    operation.current += 1;
    setAccessToken(data.access_token, data.expires_in);
    setUser(data.user); setNotice(undefined);
  };
  const register = async (input: Registration) => { await api.post('/auth/register', input); };
  const logout = async () => {
    operation.current += 1;
    setUser(undefined);
    try {
      await prepareLogout();
      await api.post('/auth/logout');
      setNotice(undefined);
    } catch (error) {
      setNotice(`Signed out locally, but server revocation could not be confirmed. Retry sign out. ${apiErrorMessage(error)}`);
    } finally {
      setAccessToken(null);
    }
  };
  return <AuthContext.Provider value={{ user, isLoading, notice, refreshProfile, login, register, logout }}>{children}</AuthContext.Provider>;
}
export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuthContext must be used within an AuthProvider');
  return context;
}
