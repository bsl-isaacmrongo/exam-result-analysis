/**
 * Only allow same-app relative paths as post-login redirects, preventing
 * open redirects such as `//evil.com` or `/\evil.com`.
 */
export function safeReturnUrl(url: string | null | undefined): string {
  if (!url || !url.startsWith('/') || url.startsWith('//') || url.startsWith('/\\')) {
    return '/';
  }
  if (url === '/login' || url.startsWith('/login?') || url.startsWith('/login#')) {
    return '/';
  }
  return url;
}
