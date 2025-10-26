import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import api from '@api/client';
import type { UserProfile } from '@/types/user';

interface AuthContextValue {
  isLoading: boolean;
  user?: UserProfile;
  refreshProfile: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export interface AuthProviderProps {
  readonly children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserProfile>();
  const [isLoading, setIsLoading] = useState(true);

  const refreshProfile = async () => {
    try {
      setIsLoading(true);
      const response = await api.get<UserProfile>('/users/me');
      setUser(response.data);
    } catch (error) {
      console.warn('Unable to load profile', error);
      setUser(undefined);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshProfile();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isLoading,
      user,
      refreshProfile
    }),
    [isLoading, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }

  return context;
}
