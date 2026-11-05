import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  convertToParamMap,
  provideRouter,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';

import { pickSchoolGuard, schoolGuard } from './school.guard';
import { School } from './school.models';
import { SchoolService } from './school.service';

const SCHOOLS: School[] = [
  { code: 'bge', name: 'Braeburn Garden Estate', curricula: ['ib'], is_active: true },
];

describe('school guards', () => {
  let forCurriculum: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    forCurriculum = vi.fn().mockResolvedValue(SCHOOLS);
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: SchoolService, useValue: { forCurriculum } }],
    });
  });

  const snapshot = (params: Record<string, string>) =>
    ({ paramMap: convertToParamMap(params) }) as ActivatedRouteSnapshot;

  const url = (result: unknown) => TestBed.inject(Router).serializeUrl(result as UrlTree);

  async function run(curriculum: string, school: string): Promise<unknown> {
    return TestBed.runInInjectionContext(() =>
      schoolGuard(snapshot({ curriculum, school }), {} as RouterStateSnapshot),
    );
  }

  it.each(['bge', 'all'])('allows %s', async (school) => {
    expect(await run('ib', school)).toBe(true);
    expect(forCurriculum).toHaveBeenCalledWith('ib');
  });

  it('reopens the picker for an unknown school', async () => {
    const result = await run('ib', 'nope');
    expect(result).toBeInstanceOf(UrlTree);
    expect(url(result)).toBe('/curricula?curriculum=ib');
  });

  it('rejects "all" when no school offers the curriculum', async () => {
    forCurriculum.mockResolvedValue([]);
    expect(url(await run('ib', 'all'))).toBe('/curricula?curriculum=ib');
  });

  it('falls back to the picker when the API fails', async () => {
    forCurriculum.mockRejectedValue(new Error('down'));
    expect(url(await run('ib', 'bge'))).toBe('/curricula?curriculum=ib');
  });

  it('skips the API for unavailable curricula', async () => {
    expect(url(await run('igcse', 'bge'))).toBe('/curricula');
    expect(forCurriculum).not.toHaveBeenCalled();
  });

  it('sends /:curriculum to the school picker', () => {
    const result = TestBed.runInInjectionContext(() =>
      pickSchoolGuard(snapshot({ curriculum: 'ib' }), {} as RouterStateSnapshot),
    );
    expect(url(result)).toBe('/curricula?curriculum=ib');
  });
});
