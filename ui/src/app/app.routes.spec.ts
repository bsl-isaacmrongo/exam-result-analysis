import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { routes } from './app.routes';
import { AuthService } from './core/auth/auth.service';
import { SchoolService } from './core/school/school.service';

const SCHOOL = { code: 'bge', name: 'Braeburn Garden Estate', curricula: ['ib'], is_active: true };

describe('School settings navigation', () => {
  // Lazy chunks are slow to transform on first import; load them outside the per-test timeout.
  beforeAll(async () => {
    await Promise.all([
      import('./core/layout/dashboard.layout'),
      import('./features/settings/schools'),
      import('./features/dashboard/overview/overview'),
    ]);
  }, 60_000);

  beforeEach(() => {
    const user = { id: 1, email: 'admin@example.com', name: null, role: 'admin' };
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        {
          provide: AuthService,
          useValue: { user: signal(user), ensureSession: vi.fn().mockResolvedValue(user) },
        },
        {
          provide: SchoolService,
          useValue: {
            cached: vi.fn().mockReturnValue([SCHOOL]),
            forCurriculum: vi.fn().mockResolvedValue([SCHOOL]),
            listAll: vi.fn().mockResolvedValue([SCHOOL]),
          },
        },
      ],
    });
  });

  it.each(['bge', 'all'])('redirects existing Settings links for %s to Schools', async (school) => {
    const harness = await RouterTestingHarness.create(`/ib/${school}/settings`);
    await harness.fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe(`/ib/${school}/settings/schools`);
    const el = harness.routeNativeElement!;
    expect(el.querySelector('h1')?.textContent).toBe('Schools');
    expect(el.querySelector('tbody')?.textContent).toContain(SCHOOL.name);
    expect(el.querySelector('nav[aria-label="Breadcrumb"] [aria-current="page"]')?.textContent)
      .toContain('Schools');
    const link = el.querySelector<HTMLAnchorElement>('a[href$="/settings/schools"]')!;
    expect(link.getAttribute('aria-current')).toBe('page');
    const toggle = el.querySelector<HTMLButtonElement>('button[aria-controls="submenu-settings"]')!;
    expect(toggle.textContent).toContain('Settings');
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(link.closest('ul')?.hidden).toBe(false);
  });

  it('toggles the Settings sub-menu', async () => {
    const harness = await RouterTestingHarness.create('/ib/bge/overview');
    await harness.fixture.whenStable();
    const el = harness.routeNativeElement!;
    const toggle = el.querySelector<HTMLButtonElement>('button[aria-controls="submenu-settings"]')!;
    const submenu = el.querySelector<HTMLUListElement>('#submenu-settings')!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(submenu.hidden).toBe(true);

    toggle.click();
    await harness.fixture.whenStable();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(submenu.hidden).toBe(false);
    expect(TestBed.inject(Router).url).toBe('/ib/bge/overview');

    toggle.click();
    await harness.fixture.whenStable();
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(submenu.hidden).toBe(true);
  });

  it('opens Schools from the sidebar and closes the mobile navigation', async () => {
    const harness = await RouterTestingHarness.create('/ib/bge/overview');
    await harness.fixture.whenStable();
    const el = harness.routeNativeElement!;
    el.querySelector<HTMLButtonElement>('button[aria-label="Open navigation"]')!.click();
    await harness.fixture.whenStable();
    expect(el.querySelector('#dashboard-sidebar')?.classList.contains('translate-x-0')).toBe(true);

    el.querySelector<HTMLButtonElement>('button[aria-controls="submenu-settings"]')!.click();
    await harness.fixture.whenStable();
    el.querySelector<HTMLAnchorElement>('a[href$="/settings/schools"]')!.click();
    await harness.fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/ib/bge/settings/schools');
    expect(el.querySelector('h1')?.textContent).toBe('Schools');
    expect(el.querySelector('#dashboard-sidebar')?.classList.contains('translate-x-0')).toBe(false);
    expect(el.querySelector('a[href$="/overview"]')?.getAttribute('aria-current')).toBeNull();
  });
});
