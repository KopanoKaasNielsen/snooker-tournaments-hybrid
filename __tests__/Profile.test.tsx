import { fireEvent, render, screen } from '@testing-library/react';
import Profile from '@/pages/Profile';
import { AuthContext } from '@/context/AuthContext';
import type { UserProfile } from '@/types/user';

describe('Profile page', () => {
  const createRefreshMock = () => jest.fn().mockResolvedValue(undefined);

  it('shows loading indicator while profile is being fetched', () => {
    const refreshProfile = createRefreshMock();
    render(
      <AuthContext.Provider value={{ isLoading: true, user: undefined, refreshProfile }}>
        <Profile />
      </AuthContext.Provider>
    );

    expect(screen.getByText(/loading your profile/i)).toBeInTheDocument();
  });

  it('shows a retry action when no user is loaded', () => {
    const refreshProfile = createRefreshMock();
    render(
      <AuthContext.Provider value={{ isLoading: false, user: undefined, refreshProfile }}>
        <Profile />
      </AuthContext.Provider>
    );

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    expect(refreshProfile).toHaveBeenCalledTimes(1);
  });

  it('renders profile information for the authenticated user', () => {
    const user: UserProfile = {
      id: 'user-1',
      username: 'Ronnie',
      email: 'ronnie@example.com',
      ranking: 1,
      walletBalance: 50250,
      favouriteCue: 'Custom ash'
    };
    const refreshProfile = createRefreshMock();

    render(
      <AuthContext.Provider value={{ isLoading: false, user, refreshProfile }}>
        <Profile />
      </AuthContext.Provider>
    );

    expect(screen.getByRole('heading', { name: /welcome back, ronnie/i })).toBeInTheDocument();
    expect(screen.getByText(user.email)).toBeInTheDocument();
    expect(screen.getByText(/50,250/)).toBeInTheDocument();
  });
});
