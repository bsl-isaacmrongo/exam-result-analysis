import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { API_BASE_URL } from '../api/api-config';
import { AuthService } from './auth.service';

/**
 * When any API call (other than the auth endpoints themselves) returns 401,
 * the session has expired or been revoked: drop local state and go to login.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const authApi = `${inject(API_BASE_URL)}/api/auth/`;

  return next(req).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !req.url.startsWith(authApi)
      ) {
        auth.clearSession();
        const returnUrl = router.url;
        void router.navigate(['/login'], {
          queryParams: { returnUrl, reason: 'expired' },
        });
      }
      return throwError(() => error);
    }),
  );
};
