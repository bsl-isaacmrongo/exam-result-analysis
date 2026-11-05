import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';

import { Icon } from '../../shared/ui/icon';
import { Curriculum } from '../curriculum/curricula';
import { ALL_SCHOOLS, School } from './school.models';
import { SchoolService } from './school.service';

/**
 * Modal asking which school's analytics to open for a curriculum. Call `open(curriculum)`;
 * on confirm it navigates to `/<curriculum>/<school>/overview`.
 */
@Component({
  selector: 'app-school-picker',
  imports: [NgTemplateOutlet, Icon],
  templateUrl: './school-picker.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SchoolPicker {
  private readonly router = inject(Router);
  private readonly schoolService = inject(SchoolService);
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  protected readonly allSchools = ALL_SCHOOLS;
  protected readonly loading = signal(false);
  protected readonly error = signal(false);
  protected readonly navigating = signal(false);
  protected readonly selected = signal<string | null>(null);
  protected readonly curriculum = signal<Curriculum | null>(null);

  protected readonly schools = computed<readonly School[]>(() => {
    const slug = this.curriculum()?.slug;
    return (slug && this.schoolService.cached(slug)) || [];
  });

  /** `current` pre-selects a school, e.g. the one the dashboard is showing. */
  open(curriculum: Curriculum, current: string | null = null): void {
    this.curriculum.set(curriculum);
    this.selected.set(current);
    this.navigating.set(false);
    const dialog = this.dialog().nativeElement;
    if (!dialog.open) dialog.showModal();
    void this.load();
  }

  close(): void {
    this.dialog().nativeElement.close();
  }

  protected async load(): Promise<void> {
    const slug = this.curriculum()?.slug;
    if (!slug) return;
    // Show the cached list straight away and refresh it quietly in the background.
    this.loading.set(this.schoolService.cached(slug) === undefined);
    this.error.set(false);
    try {
      await this.schoolService.forCurriculum(slug, { refresh: true });
    } catch {
      this.error.set(this.schoolService.cached(slug) === undefined);
    } finally {
      this.loading.set(false);
    }
  }

  /** Clicks on the backdrop land on the <dialog> element itself. */
  protected onDialogClick(event: MouseEvent): void {
    if (event.target === this.dialog().nativeElement) this.close();
  }

  protected async confirm(): Promise<void> {
    const slug = this.curriculum()?.slug;
    const code = this.selected();
    if (!slug || !code || this.navigating()) return;
    this.navigating.set(true);
    const navigated = await this.router.navigate(['/', slug, code, 'overview']);
    this.navigating.set(false);
    if (navigated !== false) this.close();
  }
}
