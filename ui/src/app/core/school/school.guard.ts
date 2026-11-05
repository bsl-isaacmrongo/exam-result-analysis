import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivateFn, Router, UrlTree } from '@angular/router';

import { findCurriculum } from '../curriculum/curricula';
import { ALL_SCHOOLS } from './school.models';
import { SchoolService } from './school.service';

/** Back to the curriculum picker, reopening the school dialog for `curriculum`. */
export function schoolPickerUrl(router: Router, curriculum: string | null): UrlTree {
  const known = findCurriculum(curriculum)?.available ? curriculum : null;
  return router.createUrlTree(['/curricula'], known ? { queryParams: { curriculum } } : {});
}

/**
 * `/:curriculum/:school/...` needs a school offering that curriculum, or `all`
 * when at least one does. Relies on params being inherited from the parent route.
 */
export const schoolGuard: CanActivateFn = async (route: ActivatedRouteSnapshot) => {
  const router = inject(Router);
  const schools = inject(SchoolService);
  const curriculum = route.paramMap.get('curriculum');
  const code = route.paramMap.get('school');

  if (curriculum && findCurriculum(curriculum)?.available) {
    try {
      const list = await schools.forCurriculum(curriculum);
      const valid = code === ALL_SCHOOLS ? list.length > 0 : list.some((s) => s.code === code);
      if (valid) return true;
    } catch {
      // Unreachable API: fall back to the picker, which shows the error and a retry.
    }
  }
  return schoolPickerUrl(router, curriculum);
};

/** `/:curriculum` without a school: ask which school first. */
export const pickSchoolGuard: CanActivateFn = (route) =>
  schoolPickerUrl(inject(Router), route.paramMap.get('curriculum'));
