import { Location, NgTemplateOutlet } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { LucideArrowLeft } from '@lucide/angular';

import { CURRICULA, Curriculum, findCurriculum } from '../../core/curriculum/curricula';
import { ALL_SCHOOLS } from '../../core/school/school.models';
import { SchoolPicker } from '../../core/school/school-picker';

/** Step between sign-in and the dashboard: pick a curriculum, then a school. */
@Component({
  selector: 'app-select-curriculum',
  imports: [NgTemplateOutlet, LucideArrowLeft, SchoolPicker],
  templateUrl: './select-curriculum.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SelectCurriculum implements AfterViewInit {
  private readonly location = inject(Location);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly picker = viewChild.required(SchoolPicker);

  protected readonly curricula = CURRICULA;

  ngAfterViewInit(): void {
    // `?curriculum=ib` (set by the dashboard guards) reopens the school dialog.
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const requested = findCurriculum(params.get('curriculum'));
      if (!requested) return;
      void this.router.navigate([], { queryParams: {}, replaceUrl: true });
      if (requested.available) this.chooseSchool(requested);
    });
  }

  protected chooseSchool(curriculum: Curriculum): void {
    this.picker().open(curriculum);
  }

  protected goBack(): void {
    // Only step back within the app; on a fresh load there is nothing to return to,
    // so try the default curriculum's combined view (the guards fall back to this page).
    if (this.router.lastSuccessfulNavigation()?.previousNavigation) {
      this.location.back();
      return;
    }
    const fallback = this.curricula.find((c) => c.available);
    if (fallback) void this.router.navigate(['/', fallback.slug, ALL_SCHOOLS, 'overview']);
  }
}
