import { DOCUMENT } from '@angular/common';
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { API_BASE_URL } from './api-config';

export const CSRF_COOKIE = 'XSRF-TOKEN';
export const CSRF_HEADER = 'X-XSRF-TOKEN';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

/**
 * For requests to our API only:
 *  - send cookies (the HttpOnly session cookie) cross-origin, and
 *  - echo the CSRF cookie in the X-XSRF-TOKEN header on mutating requests.
 *
 * Angular's built-in XSRF support skips absolute URLs, hence this interceptor.
 * Requests to any other host are left untouched, so neither cookies nor the
 * CSRF token can leak to third parties.
 */
export const apiInterceptor: HttpInterceptorFn = (req, next) => {
  const baseUrl = inject(API_BASE_URL);
  if (req.url !== baseUrl && !req.url.startsWith(`${baseUrl}/`)) {
    return next(req);
  }

  let headers = req.headers;
  if (!SAFE_METHODS.has(req.method) && !headers.has(CSRF_HEADER)) {
    const token = readCookie(inject(DOCUMENT).cookie, CSRF_COOKIE);
    if (token) headers = headers.set(CSRF_HEADER, token);
  }
  return next(req.clone({ withCredentials: true, headers }));
};

function readCookie(cookies: string, name: string): string | null {
  for (const part of cookies.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) return decodeURIComponent(rest.join('='));
  }
  return null;
}
