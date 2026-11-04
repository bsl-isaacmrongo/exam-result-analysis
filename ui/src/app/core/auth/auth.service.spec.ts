import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService, authErrorMessage, googleSsoErrorMessage } from './auth.service';

const USER = { id: 1, email: 'staff@example.org', name: 'Staff', role: 'user' };

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('treats 401 from /me as signed out and caches the result', async () => {
    const first = service.ensureSession();
    http.expectOne('http://localhost:8000/api/auth/me').flush({ detail: 'x' }, { status: 401, statusText: 'Unauthorized' });
    expect(await first).toBeNull();
    expect(await service.ensureSession()).toBeNull();
    http.expectNone('http://localhost:8000/api/auth/me');
  });

  it('signs in with password and exposes the user', async () => {
    const login = service.loginWithPassword('  staff@example.org ', 'pw');
    const req = http.expectOne('http://localhost:8000/api/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'staff@example.org', password: 'pw' });
    req.flush(USER);
    await login;
    expect(service.user()).toEqual(USER);
    expect(service.isAuthenticated()).toBe(true);
  });

  it('clears the user on logout even if the request fails', async () => {
    const login = service.loginWithPassword('staff@example.org', 'pw');
    http.expectOne('http://localhost:8000/api/auth/login').flush(USER);
    await login;

    const logout = service.logout();
    http.expectOne('http://localhost:8000/api/auth/logout').error(new ProgressEvent('error'));
    await expect(logout).rejects.toBeTruthy();
    expect(service.user()).toBeNull();
  });
});

describe('authErrorMessage', () => {
  const err = (status: number, error: unknown = null) =>
    new HttpErrorResponse({ status, error });

  it('shows server detail for auth failures', () => {
    expect(authErrorMessage(err(401, { detail: 'Invalid email or password' }))).toBe(
      'Invalid email or password',
    );
  });

  it('does not leak unexpected server errors', () => {
    expect(authErrorMessage(err(500, { detail: 'Traceback ...' }))).toBe(
      'Sign-in failed. Please try again.',
    );
  });

  it('handles network failures', () => {
    expect(authErrorMessage(err(0))).toContain('Cannot reach the server');
  });
});

describe('Google SSO', () => {
  it('builds the API start URL with an encoded return path', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient()] });
    const service = TestBed.inject(AuthService);
    expect(service.googleLoginUrl('/reports?year=2026')).toBe(
      'http://localhost:8000/api/auth/google/login?return_url=%2Freports%3Fyear%3D2026',
    );
  });

  it('maps known error codes and never echoes unknown ones', () => {
    expect(googleSsoErrorMessage(null)).toBeNull();
    expect(googleSsoErrorMessage('google_not_authorized')).toContain('not been granted access');
    expect(googleSsoErrorMessage('<script>alert(1)</script>')).toBe(
      'Google sign-in failed. Please try again.',
    );
    expect(googleSsoErrorMessage('__proto__')).toBe('Google sign-in failed. Please try again.');
  });
});
