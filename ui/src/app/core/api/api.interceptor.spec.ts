import { DOCUMENT } from '@angular/common';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API_BASE_URL } from './api-config';
import { CSRF_HEADER, apiInterceptor } from './api.interceptor';

describe('apiInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiInterceptor])),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: 'http://localhost:8000' },
        { provide: DOCUMENT, useValue: { cookie: 'other=1; XSRF-TOKEN=abc%3D123' } },
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => backend.verify());

  it('sends credentials and the CSRF header on API mutations', () => {
    http.post('http://localhost:8000/api/auth/logout', null).subscribe();
    const req = backend.expectOne('http://localhost:8000/api/auth/logout');
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.get(CSRF_HEADER)).toBe('abc=123');
  });

  it('sends credentials but no CSRF header on GET', () => {
    http.get('http://localhost:8000/api/auth/me').subscribe();
    const req = backend.expectOne('http://localhost:8000/api/auth/me');
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.has(CSRF_HEADER)).toBe(false);
  });

  it('leaves other hosts untouched', () => {
    for (const url of ['https://example.com/x', 'http://localhost:8000.evil.com/x']) {
      http.post(url, null).subscribe();
      const req = backend.expectOne(url);
      expect(req.request.withCredentials).toBe(false);
      expect(req.request.headers.has(CSRF_HEADER)).toBe(false);
    }
  });
});
