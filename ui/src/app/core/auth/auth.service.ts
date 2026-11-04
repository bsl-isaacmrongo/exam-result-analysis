import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { API_BASE_URL } from '../api/api-config';
import { AuthOptions, AuthUser } from './auth.models';

/**
 * Session state. The session lives in an HttpOnly cookie the browser manages;
 * no token is ever readable from JavaScript or stored in localStorage.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly api = `${inject(API_BASE_URL)}/api/auth`;
  private readonly currentUser = signal<AuthUser | null>(null);
  private sessionCheck: Promise<AuthUser | null> | null = null;

  readonly user = this.currentUser.asReadonly();
  readonly isAuthenticated = computed(() => this.currentUser() !== null);

  /** Resolves the current session once per app load (cached). */
  ensureSession(): Promise<AuthUser | null> {
    this.sessionCheck ??= firstValueFrom(this.http.get<AuthUser>(`${this.api}/me`)).then(
      (user) => this.setUser(user),
      (error: unknown) => {
        if (error instanceof HttpErrorResponse && error.status === 401) {
          return this.setUser(null);
        }
        // Network/server error: don't cache, allow a retry on next navigation.
        this.sessionCheck = null;
        throw error;
      },
    );
    return this.sessionCheck;
  }

  getOptions(): Promise<AuthOptions> {
    return firstValueFrom(this.http.get<AuthOptions>(`${this.api}/options`));
  }

  async loginWithPassword(email: string, password: string): Promise<AuthUser> {
    const user = await firstValueFrom(
      this.http.post<AuthUser>(`${this.api}/login`, { email: email.trim(), password }),
    );
    return this.setUser(user);
  }

  /**
   * URL that starts Google SSO. The browser navigates there (full page); the
   * API redirects to Google and, after the callback, back into the app.
   */
  googleLoginUrl(returnUrl: string): string {
    return `${this.api}/google/login?return_url=${encodeURIComponent(returnUrl)}`;
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.http.post<void>(`${this.api}/logout`, null));
    } finally {
      this.clearSession();
    }
  }

  /** Forget the local session (e.g. after the server answers 401). */
  clearSession(): void {
    this.setUser(null);
  }

  private setUser<T extends AuthUser | null>(user: T): T {
    this.currentUser.set(user);
    this.sessionCheck = Promise.resolve(user);
    return user;
  }
}

const GOOGLE_SSO_ERRORS: Record<string, string> = {
  google_cancelled: 'Google sign-in was cancelled.',
  google_not_authorized:
    'This Google account has not been granted access. Contact your system administrator.',
  google_unavailable:
    'Google sign-in is unavailable right now. Please try again or use your email and password.',
  google_failed: 'Google sign-in failed. Please try again.',
};

/** Message for the `?error=` code the API appends after a failed Google SSO. */
export function googleSsoErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return Object.hasOwn(GOOGLE_SSO_ERRORS, code)
    ? GOOGLE_SSO_ERRORS[code]
    : GOOGLE_SSO_ERRORS['google_failed'];
}

/** Turn an API error into a message that is safe to show on the login page. */
export function authErrorMessage(error: unknown): string {
  if (!(error instanceof HttpErrorResponse)) {
    return 'Something went wrong. Please try again.';
  }
  if (error.status === 0) {
    return 'Cannot reach the server. Check your connection and try again.';
  }
  if (error.status === 422) {
    return 'Please enter a valid email address and password.';
  }
  const detail = (error.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && [401, 403, 429, 503].includes(error.status)) {
    return detail;
  }
  return 'Sign-in failed. Please try again.';
}
