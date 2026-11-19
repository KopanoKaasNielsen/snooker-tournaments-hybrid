import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import type { UserProfile } from '@/types/user';

interface AuthContextValue {
  isLoading: boolean;
  profileAvailable?: boolean;
  user?: UserProfile;
  refreshProfile: () => Promise<void>;
}
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
// No identity is inferred from public player records. Enable auth only with a backend contract.
const unavailable: AuthContextValue = { isLoading: false, profileAvailable: false, refreshProfile: async () => {} };
export function AuthProvider({ children }: { readonly children: ReactNode }) {
  return <AuthContext.Provider value={unavailable}>{children}</AuthContext.Provider>;
}
export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuthContext must be used within an AuthProvider');
  return context;
}
