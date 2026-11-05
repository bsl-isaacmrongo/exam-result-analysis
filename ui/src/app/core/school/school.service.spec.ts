import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { School } from './school.models';
import { SchoolService, schoolErrorMessage } from './school.service';

const URL = 'http://localhost:8000/api/schools?curriculum=ib';
const SCHOOLS: School[] = [
  { code: 'bge', name: 'Braeburn Garden Estate', curricula: ['ib'], is_active: true },
];

describe('SchoolService', () => {
  let service: SchoolService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SchoolService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('fetches once per curriculum and caches the result', async () => {
    expect(service.cached('ib')).toBeUndefined();
    const first = service.forCurriculum('ib');
    const second = service.forCurriculum('ib');
    http.expectOne(URL).flush(SCHOOLS);
    expect(await first).toEqual(SCHOOLS);
    expect(await second).toEqual(SCHOOLS);
    expect(await service.forCurriculum('ib')).toEqual(SCHOOLS);
    expect(service.cached('ib')).toEqual(SCHOOLS);
  });

  it('refetches on refresh', async () => {
    const first = service.forCurriculum('ib');
    http.expectOne(URL).flush(SCHOOLS);
    await first;
    const refreshed = service.forCurriculum('ib', { refresh: true });
    http.expectOne(URL).flush([]);
    expect(await refreshed).toEqual([]);
    expect(service.cached('ib')).toEqual([]);
  });

  it('does not cache failures', async () => {
    const failed = service.forCurriculum('ib');
    http.expectOne(URL).flush(null, { status: 500, statusText: 'Server Error' });
    await expect(failed).rejects.toBeTruthy();
    expect(service.cached('ib')).toBeUndefined();
    const retry = service.forCurriculum('ib');
    http.expectOne(URL).flush(SCHOOLS);
    expect(await retry).toEqual(SCHOOLS);
  });
});

describe('SchoolService admin calls', () => {
  let service: SchoolService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SchoolService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates a school and refreshes cached curricula', async () => {
    const cached = service.forCurriculum('ib');
    http.expectOne(URL).flush([]);
    await cached;

    const created = service.create({ code: 'bge', name: 'BGE', curricula: ['ib'] });
    const req = http.expectOne('http://localhost:8000/api/schools');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ code: 'bge', name: 'BGE', curricula: ['ib'] });
    req.flush(SCHOOLS[0]);
    expect(await created).toEqual(SCHOOLS[0]);

    http.expectOne(URL).flush(SCHOOLS);
    await Promise.resolve();
    expect(service.cached('ib')).toEqual(SCHOOLS);
  });

  it('lists all schools including inactive', async () => {
    const all = service.listAll();
    http.expectOne('http://localhost:8000/api/schools?include_inactive=true').flush(SCHOOLS);
    expect(await all).toEqual(SCHOOLS);
  });
});

describe('schoolErrorMessage', () => {
  const error = (status: number, detail: unknown) =>
    new HttpErrorResponse({ status, error: { detail } });

  it('flags the code on conflict', () => {
    expect(schoolErrorMessage(error(409, "School 'bge' already exists"))).toEqual({
      message: "School 'bge' already exists",
      fields: { code: 'This code is already used by another school.' },
    });
  });

  it('maps validation errors to fields', () => {
    const result = schoolErrorMessage(
      error(422, [
        { loc: ['body', 'code'], msg: "Value error, 'all' is reserved" },
        { loc: ['body', 'curricula'], msg: 'Value error, unknown curriculum' },
      ]),
    );
    expect(result.fields).toEqual({ code: "'all' is reserved", curricula: 'unknown curriculum' });
  });

  it('explains forbidden and offline errors', () => {
    expect(schoolErrorMessage(error(403, 'x')).message).toMatch(/administrators/);
    expect(schoolErrorMessage(error(0, null)).message).toMatch(/reach the server/);
  });
});
