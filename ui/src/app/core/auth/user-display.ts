import { AuthUser } from './auth.models';

export function displayName(user: AuthUser | null): string {
  return user?.name?.trim() || user?.email || '';
}

/** Up to two initials from the name, or from the email's local part. */
export function userInitials(user: AuthUser | null): string {
  if (!user) return '';
  const source = user.name?.trim() || user.email.split('@')[0];
  const words = source.split(/[\s._-]+/).filter(Boolean);
  const initials =
    words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0] ?? '').slice(0, 2);
  return initials.toUpperCase();
}
