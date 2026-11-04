import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-home',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="min-h-dvh bg-slate-50 text-slate-900">
      <header class="border-b border-slate-200 bg-white">
        <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div class="flex items-center gap-3">
            <span
              class="grid size-9 place-items-center rounded-xl bg-brand font-display font-bold text-white"
              aria-hidden="true"
              >B</span
            >
            <span class="font-display text-lg font-semibold">Results Analysis</span>
          </div>
          <div class="flex items-center gap-4">
            <div class="hidden text-right text-sm sm:block">
              <p class="font-medium">{{ auth.user()?.name || auth.user()?.email }}</p>
              <p class="text-xs text-slate-500 capitalize">{{ auth.user()?.role }}</p>
            </div>
            <button
              type="button"
              (click)="signOut()"
              [disabled]="signingOut()"
              class="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-100 disabled:opacity-60"
            >
              {{ signingOut() ? 'Signing out…' : 'Sign out' }}
            </button>
          </div>
        </div>
      </header>

      <main class="mx-auto max-w-7xl px-6 py-10">
        <h1 class="font-display text-3xl font-semibold">
          Welcome{{ auth.user()?.name ? ', ' + auth.user()?.name : '' }}
        </h1>
        <p class="mt-2 text-slate-600">IB Diploma and Career-related Programme analysis.</p>
      </main>
    </div>
  `,
})
export class Home {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected readonly signingOut = signal(false);

  protected async signOut(): Promise<void> {
    this.signingOut.set(true);
    try {
      await this.auth.logout();
    } catch {
      // Local session is cleared regardless; the server session expires on its own.
    } finally {
      await this.router.navigateByUrl('/login', { replaceUrl: true });
    }
  }
}
