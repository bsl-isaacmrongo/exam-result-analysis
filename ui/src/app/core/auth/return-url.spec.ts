import { safeReturnUrl } from './return-url';

describe('safeReturnUrl', () => {
  it('keeps internal paths', () => {
    expect(safeReturnUrl('/reports/ib?year=2026')).toBe('/reports/ib?year=2026');
  });

  it.each([null, '', 'https://evil.com', '//evil.com', '/\\evil.com', 'javascript:alert(1)', '/login', '/login?returnUrl=/x'])(
    'rejects %s',
    (url) => {
      expect(safeReturnUrl(url)).toBe('/');
    },
  );
});
