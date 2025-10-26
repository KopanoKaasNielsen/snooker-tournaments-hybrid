import { fireEvent, render, screen } from '@testing-library/react';
import Settings from '@/pages/Settings';
import { AuthContext } from '@/context/AuthContext';
import type { UserProfile } from '@/types/user';

function renderSettings(user?: UserProfile) {
  return render(
    <AuthContext.Provider value={{ isLoading: false, user, refreshProfile: jest.fn() }}>
      <Settings />
    </AuthContext.Provider>
  );
}

describe('Settings page', () => {
  it('submits preference updates and displays confirmation message', () => {
    renderSettings();

    fireEvent.click(screen.getByRole('button', { name: /save preferences/i }));

    expect(screen.getByText(/preferences saved/i)).toBeInTheDocument();
  });

  it('prefills the practice table using the player ranking', () => {
    const user: UserProfile = {
      id: 'user-1',
      username: 'Judd',
      email: 'judd@example.com',
      ranking: 2,
      walletBalance: 30000
    };

    renderSettings(user);

    const input = screen.getByLabelText(/preferred practice table/i) as HTMLInputElement;
    expect(input.value).toBe(String(user.ranking));
  });
});
