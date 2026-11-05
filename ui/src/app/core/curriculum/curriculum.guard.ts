import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { findCurriculum } from './curricula';

/** Dashboard routes need a known, available curriculum; otherwise pick one first. */
export const curriculumGuard: CanActivateFn = (route) => {
  const curriculum = findCurriculum(route.paramMap.get('curriculum'));
  return curriculum?.available ? true : inject(Router).createUrlTree(['/curricula']);
};
