import { InjectionToken } from '@angular/core';

import { environment } from '../../../environments/environment';

/** Backend origin without a trailing slash, e.g. `http://localhost:8000`. */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => environment.apiBaseUrl.replace(/\/+$/, ''),
});
