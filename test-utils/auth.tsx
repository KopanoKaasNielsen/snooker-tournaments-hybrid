import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { AuthContext } from '@/context/AuthContext';
import type { AuthContextValue } from '@/context/AuthContext';
import type { UserProfile } from '@/types/user';
export const testUser: UserProfile = { id: 1, username: 'Test Player', role: 'player', player_id: 1, is_active: true };
export function authValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return { isLoading: false, user: testUser, refreshProfile: jest.fn().mockResolvedValue(undefined),
    login: jest.fn().mockResolvedValue(undefined), register: jest.fn().mockResolvedValue(undefined),
    logout: jest.fn().mockResolvedValue(undefined), ...overrides };
}
export function renderWithAuth(element: ReactElement, overrides: Partial<AuthContextValue> = {}) {
  return render(<AuthContext.Provider value={authValue(overrides)}>{element}</AuthContext.Provider>);
}
