import { Location, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { LucideArrowLeft } from '@lucide/angular';

import { CURRICULA } from '../../core/curriculum/curricula';

/** Step between sign-in and the dashboard: pick whose results to analyse. */
@Component({
  selector: 'app-select-curriculum',
  imports: [NgTemplateOutlet, RouterLink, LucideArrowLeft],
  templateUrl: './select-curriculum.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SelectCurriculum {
  private readonly location = inject(Location);
  private readonly router = inject(Router);

  protected readonly curricula = CURRICULA;

  protected goBack(): void {
    // Only step back within the app; on a fresh load there is nothing to return to,
    // so fall back to the default curriculum's dashboard.
    if (this.router.lastSuccessfulNavigation()?.previousNavigation) {
      this.location.back();
      return;
    }
    const fallback = this.curricula.find((c) => c.available);
    if (fallback) void this.router.navigate(['/', fallback.slug, 'overview']);
  }
}
