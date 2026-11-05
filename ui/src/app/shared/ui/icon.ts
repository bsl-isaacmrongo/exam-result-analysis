import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  LucideArrowLeftRight,
  LucideBookOpen,
  LucideChevronRight,
  LucideChevronsUpDown,
  LucideClock,
  LucideDatabase,
  LucideDynamicIcon,
  LucideFileText,
  LucideGraduationCap,
  LucideLayoutDashboard,
  LucideLightbulb,
  LucideLogOut,
  LucideMenu,
  LucideSettings,
  LucideTrendingDown,
  LucideTrendingUp,
  LucideTriangleExclamationPoint,
  LucideUsers,
  LucideX,
} from '@lucide/angular';

/** App icon names mapped to Lucide icons (https://lucide.dev/icons). */
const ICONS = {
  overview: LucideLayoutDashboard,
  subjects: LucideBookOpen,
  cohorts: LucideUsers,
  students: LucideGraduationCap,
  reports: LucideFileText,
  imports: LucideDatabase,
  settings: LucideSettings,
  'chevron-right': LucideChevronRight,
  'chevron-up-down': LucideChevronsUpDown,
  menu: LucideMenu,
  close: LucideX,
  'sign-out': LucideLogOut,
  switch: LucideArrowLeftRight,
  'trend-up': LucideTrendingUp,
  'trend-down': LucideTrendingDown,
  bulb: LucideLightbulb,
  clock: LucideClock,
  warning: LucideTriangleExclamationPoint,
} as const;

export type IconName = keyof typeof ICONS;

/** Decorative icon; size it with classes on `<app-icon>`, e.g. `class="size-5"`. */
@Component({
  selector: 'app-icon',
  imports: [LucideDynamicIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'inline-flex shrink-0', 'aria-hidden': 'true' },
  template: `<svg [lucideIcon]="icon()" [strokeWidth]="strokeWidth()" class="size-full"></svg>`,
})
export class Icon {
  readonly name = input.required<IconName>();
  readonly strokeWidth = input(1.75);

  protected readonly icon = computed(() => ICONS[this.name()]);
}
