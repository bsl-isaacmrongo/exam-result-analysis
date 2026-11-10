import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/** Full-bleed branded frame for signed-out pages (login). */
@Component({
  selector: 'app-auth-layout',
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main
      class="relative isolate flex min-h-dvh flex-col overflow-hidden bg-slate-950 text-slate-900"
    >
      <img
        src="images/bg-login.avif"
        alt=""
        aria-hidden="true"
        fetchpriority="high"
        class="absolute inset-0 -z-20 h-full w-full object-cover"
      />
      <div aria-hidden="true" class="absolute inset-0 -z-10 bg-black/70"></div>

      <!-- <header class="flex items-center justify-between px-5 py-5 sm:px-8">
        <div class="leading-tight text-white">
          <p class="font-display text-xl font-semibold tracking-wide">BRAEBURN</p>
          <p class="text-[0.7rem] tracking-[0.3em] text-brand-accent uppercase">Results Analysis</p>
        </div>
      </header> -->

      <div class="flex flex-1 flex-col">
        <router-outlet />
      </div>

      <footer class="pb-6 text-center text-xs text-white/60">
        Access is limited to provisioned staff accounts.
      </footer>
    </main>
  `,
})
export class AuthLayout {}
