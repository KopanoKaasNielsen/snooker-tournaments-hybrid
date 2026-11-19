import { render, screen } from '@testing-library/react';
import Settings from '@/pages/Settings';

describe('Settings page', () => {
  it('explains why preferences cannot be saved', () => {
    render(<Settings />);
    expect(screen.getByText(/backend has no settings endpoint/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
  });
  it('does not invent a practice table from player ranking', () => {
    render(<Settings />);
    expect(screen.queryByLabelText(/preferred practice table/i)).not.toBeInTheDocument();
  });
});
