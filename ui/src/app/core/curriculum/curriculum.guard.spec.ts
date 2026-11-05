import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  convertToParamMap,
  provideRouter,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';

import { curriculumGuard } from './curriculum.guard';

describe('curriculumGuard', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideRouter([])] }));

  function run(slug: string): unknown {
    const route = { paramMap: convertToParamMap({ curriculum: slug }) } as ActivatedRouteSnapshot;
    return TestBed.runInInjectionContext(() => curriculumGuard(route, {} as RouterStateSnapshot));
  }

  it('allows an available curriculum', () => {
    expect(run('ib')).toBe(true);
  });

  it.each(['igcse', 'unknown'])('sends %s to the curriculum picker', (slug) => {
    const result = run(slug);
    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/curricula');
  });
});
