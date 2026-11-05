import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth/auth.guards';
import { curriculumGuard } from './core/curriculum/curriculum.guard';

const comingSoon = (path: string, label: string) => ({
  path,
  title: `${label} · Results Analysis`,
  data: { label },
  loadComponent: () =>
    import('./features/dashboard/coming-soon/coming-soon').then((m) => m.ComingSoon),
});

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'curricula' },
  {
    path: '',
    loadComponent: () => import('./core/layout/auth.layout').then((m) => m.AuthLayout),
    children: [
      {
        path: 'login',
        title: 'Sign in · Results Analysis',
        canActivate: [guestGuard],
        loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
      },
    ],
  },
  {
    path: 'curricula',
    title: 'Choose a curriculum · Results Analysis',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/curricula/select-curriculum').then((m) => m.SelectCurriculum),
  },
  {
    path: ':curriculum',
    canActivate: [authGuard, curriculumGuard],
    loadComponent: () => import('./core/layout/dashboard.layout').then((m) => m.DashboardLayout),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'overview' },
      {
        path: 'overview',
        title: 'Overview · Results Analysis',
        data: { label: 'Overview' },
        loadComponent: () =>
          import('./features/dashboard/overview/overview').then((m) => m.Overview),
      },
      comingSoon('subjects', 'Subjects'),
      comingSoon('cohorts', 'Cohorts'),
      comingSoon('students', 'Student results'),
      comingSoon('reports', 'Reports'),
      comingSoon('imports', 'Data imports'),
      comingSoon('settings', 'Settings'),
    ],
  },
  { path: '**', redirectTo: 'curricula' },
];
