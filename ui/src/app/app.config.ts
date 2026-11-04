import { provideHttpClient, withInterceptors, withNoXsrfProtection } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { apiInterceptor } from './core/api/api.interceptor';
import { authInterceptor } from './core/auth/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(
      // The API is on another origin (API_BASE_URL); apiInterceptor handles
      // credentials and the CSRF header for it instead of Angular's built-in.
      withNoXsrfProtection(),
      withInterceptors([apiInterceptor, authInterceptor]),
    ),
  ],
};
