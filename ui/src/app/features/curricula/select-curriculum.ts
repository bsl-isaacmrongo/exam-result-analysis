import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { injectSignOut } from '../../core/auth/sign-out';
import { displayName, userInitials } from '../../core/auth/user-display';
import { CURRICULA } from '../../core/curriculum/curricula';
import { LucideFileText, LucideMoveLeft, LucideArrowLeft } from '@lucide/angular';


/** Step between sign-in and the dashboard: pick whose results to analyse. */
@Component({
  selector: 'app-select-curriculum',
  imports: [NgTemplateOutlet, RouterLink, LucideFileText, LucideMoveLeft, LucideArrowLeft],
  templateUrl: './select-curriculum.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SelectCurriculum {
  private readonly auth = inject(AuthService);

  protected readonly curricula = CURRICULA;
  protected readonly signOutAction = injectSignOut();
  protected readonly userName = computed(() => displayName(this.auth.user()));
  protected readonly initials = computed(() => userInitials(this.auth.user()));
}
