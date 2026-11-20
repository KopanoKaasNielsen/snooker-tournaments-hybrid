import { fireEvent, screen } from '@testing-library/react';
import Profile from '@/pages/Profile';
import { renderWithAuth, testUser } from '../test-utils/auth';

describe('Profile page', () => {
  it('shows loading indicator while profile is being fetched', () => {
    renderWithAuth(<Profile />, { isLoading: true, user: undefined });
    expect(screen.getByText(/loading your profile/i)).toBeInTheDocument();
  });
  it('shows a retry action when no user is loaded', () => {
    const refreshProfile = jest.fn().mockResolvedValue(undefined);
    renderWithAuth(<Profile />, { user: undefined, refreshProfile });
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(refreshProfile).toHaveBeenCalledTimes(1);
  });
  it('renders the real current-user contract without invented account fields', () => {
    renderWithAuth(<Profile />);
    expect(screen.getByRole('heading', { name: `Welcome back, ${testUser.username}` })).toBeInTheDocument();
    expect(screen.getByText('player')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.queryByText(/world ranking/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/favourite cue/i)).not.toBeInTheDocument();
  });
});
