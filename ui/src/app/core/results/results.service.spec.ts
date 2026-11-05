import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { parseSessionParam, sessionLabel, sessionParam } from './results.models';
import { ResultsService, importErrorMessage } from './results.service';

const API = 'http://localhost:8000/api';

describe('ResultsService', () => {
  let service: ResultsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ResultsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('uploads the workbook as multipart form data', async () => {
    const file = new File(['x'], 'IB Results.xlsx');
    const done = service.upload({ school: 'bge', kind: 'ib_results', year: 2026, session: 'may', file });
    const req = http.expectOne(`${API}/imports`);
    expect(req.request.method).toBe('POST');
    const body = req.request.body as FormData;
    expect(body.get('school')).toBe('bge');
    expect(body.get('kind')).toBe('ib_results');
    expect(body.get('year')).toBe('2026');
    expect(body.get('session')).toBe('may');
    expect((body.get('file') as File).name).toBe('IB Results.xlsx');
    req.flush({ id: 1 });
    expect(await done).toEqual({ id: 1 });
  });

  it('requests the latest or a chosen session', async () => {
    const latest = service.analysis('bge');
    http.expectOne(`${API}/analysis/ib?school=bge`).flush({ analysis: null });
    await latest;
    const chosen = service.analysis('all', { year: 2025, session: 'nov' });
    http.expectOne(`${API}/analysis/ib?school=all&year=2025&session=nov`).flush({});
    await chosen;
  });

  it('lists and deletes imports', async () => {
    const list = service.listImports('bge');
    http.expectOne(`${API}/imports?school=bge`).flush([]);
    expect(await list).toEqual([]);
    const removed = service.remove(7);
    const req = http.expectOne(`${API}/imports/7`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null, { status: 204, statusText: 'No Content' });
    await removed;
  });
});

describe('importErrorMessage', () => {
  const error = (status: number, detail: unknown) => new HttpErrorResponse({ status, error: { detail } });

  it('shows workbook validation errors', () => {
    expect(
      importErrorMessage(error(422, { message: '2 value(s) need fixing.', errors: ['Row 4: bad'] })),
    ).toEqual({ message: '2 value(s) need fixing.', errors: ['Row 4: bad'] });
  });

  it('explains permission, size and network errors', () => {
    expect(importErrorMessage(error(403, 'x')).message).toMatch(/administrators/);
    expect(importErrorMessage(error(413, null)).message).toMatch(/too large/);
    expect(importErrorMessage(error(0, null)).message).toMatch(/reach the server/);
    expect(importErrorMessage(new Error('x')).message).toMatch(/went wrong/);
  });
});

describe('session helpers', () => {
  it('formats and parses sessions', () => {
    expect(sessionLabel({ year: 2026, session: 'nov' })).toBe('November 2026');
    expect(sessionParam({ year: 2026, session: 'may' })).toBe('2026-may');
    expect(parseSessionParam('2025-nov')).toEqual({ year: 2025, session: 'nov' });
    expect(parseSessionParam('2025-june')).toBeNull();
    expect(parseSessionParam(null)).toBeNull();
  });
});
