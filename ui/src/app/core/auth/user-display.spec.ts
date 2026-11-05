import { AuthUser } from './auth.models';
import { displayName, userInitials } from './user-display';

const user = (name: string | null, email = 'jane.doe@school.org'): AuthUser => ({
  id: 1,
  email,
  name,
  role: 'admin',
});

describe('user display helpers', () => {
  it('uses the first and last name for initials', () => {
    expect(userInitials(user('Alex Mary Carter'))).toBe('AC');
  });

  it('falls back to the email local part', () => {
    expect(userInitials(user(null))).toBe('JD');
    expect(userInitials(user(null, 'admin@school.org'))).toBe('AD');
  });

  it('prefers the name for display, then the email', () => {
    expect(displayName(user('  Jane  '))).toBe('Jane');
    expect(displayName(user(null))).toBe('jane.doe@school.org');
    expect(displayName(null)).toBe('');
  });
});
