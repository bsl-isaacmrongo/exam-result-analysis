import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import {
  ActivatedRoute,
  ActivatedRouteSnapshot,
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { filter, map } from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { injectSignOut } from '../auth/sign-out';
import { displayName, userInitials } from '../auth/user-display';
import { findCurriculum } from '../curriculum/curricula';
import { Icon, IconName } from '../../shared/ui/icon';

interface NavItem {
  path: string;
  label: string;
  icon: IconName;
}

const NAV_SECTIONS: readonly { title: string; items: readonly NavItem[] }[] = [
  {
    title: 'Workspace',
    items: [
      { path: 'overview', label: 'Overview', icon: 'overview' },
      { path: 'subjects', label: 'Subjects', icon: 'subjects' },
      { path: 'cohorts', label: 'Cohorts', icon: 'cohorts' },
      { path: 'students', label: 'Student results', icon: 'students' },
      { path: 'reports', label: 'Reports', icon: 'reports' },
    ],
  },
  {
    title: 'Manage',
    items: [
      { path: 'imports', label: 'Data imports', icon: 'imports' },
      { path: 'settings', label: 'Settings', icon: 'settings' },
    ],
  },
];

/** Sidebar + top bar shell for one curriculum's analysis pages (`/:curriculum/...`). */
@Component({
  selector: 'app-dashboard-layout',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  templateUrl: './dashboard.layout.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:keydown.escape)': 'closeOverlays()',
    '(document:click)': 'onDocumentClick($event)',
  },
})
export class DashboardLayout {
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly auth = inject(AuthService);
  private readonly userMenuRef = viewChild<ElementRef<HTMLElement>>('userMenu');

  protected readonly navSections = NAV_SECTIONS;
  protected readonly sidebarOpen = signal(false);
  protected readonly userMenuOpen = signal(false);
  protected readonly signOutAction = injectSignOut();

  protected readonly curriculum = toSignal(
    this.route.paramMap.pipe(map((params) => findCurriculum(params.get('curriculum')))),
    { initialValue: findCurriculum(this.route.snapshot.paramMap.get('curriculum')) },
  );

  /** `label` from the deepest active child route, for the breadcrumb. */
  protected readonly pageLabel = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map(() => this.currentLabel()),
    ),
    { initialValue: this.currentLabel() },
  );

  protected readonly userName = computed(() => displayName(this.auth.user()));
  protected readonly initials = computed(() => userInitials(this.auth.user()));
  protected readonly role = computed(() => this.auth.user()?.role ?? '');

  constructor() {
    // Close the mobile drawer and menus after any navigation.
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.closeOverlays());
  }

  protected closeOverlays(): void {
    this.sidebarOpen.set(false);
    this.userMenuOpen.set(false);
  }

  protected onDocumentClick(event: MouseEvent): void {
    const menu = this.userMenuRef()?.nativeElement;
    if (this.userMenuOpen() && menu && !menu.contains(event.target as Node)) {
      this.userMenuOpen.set(false);
    }
  }

  private currentLabel(): string {
    let snapshot: ActivatedRouteSnapshot | null = this.route.snapshot;
    let label = '';
    while (snapshot) {
      label = (snapshot.data['label'] as string | undefined) ?? label;
      snapshot = snapshot.firstChild;
    }
    return label;
  }
}
