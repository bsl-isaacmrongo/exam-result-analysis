import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { Icon } from '../../../shared/ui/icon';

/** Placeholder for dashboard sections that are not built yet. */
@Component({
  selector: 'app-coming-soon',
  imports: [Icon, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="mx-auto mt-10 max-w-lg rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center"
    >
      <span
        class="mx-auto grid size-12 place-items-center rounded-full bg-slate-100 text-slate-500"
      >
        <app-icon name="clock" class="size-6" />
      </span>
      <h1 class="mt-4 text-xl font-semibold text-slate-900">{{ label() }}</h1>
      <p class="mt-2 text-sm text-slate-500">This section is coming soon.</p>
      <a
        routerLink="../overview"
        class="mt-6 inline-block text-sm font-semibold text-brand hover:underline"
        >Back to overview</a
      >
    </div>
  `,
})
export class ComingSoon {
  protected readonly label = toSignal(
    inject(ActivatedRoute).data.pipe(map((d) => (d['label'] as string) ?? 'Coming soon')),
    { initialValue: '' },
  );
}
