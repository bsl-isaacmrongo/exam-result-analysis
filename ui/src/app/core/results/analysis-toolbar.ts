import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import {
  ExamSession,
  PATHWAY_LABELS,
  Pathway,
  parseSessionParam,
  sessionLabel,
  sessionParam,
} from './results.models';

/** Exam session picker and DP / CP / Combined toggle shared by the analysis pages. */
@Component({
  selector: 'app-analysis-toolbar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'flex flex-wrap items-center gap-3' },
  template: `
    @if (sessions().length > 1) {
      <label class="sr-only" for="analysis-session">Exam session</label>
      <select
        id="analysis-session"
        class="rounded-lg border border-slate-300 bg-white py-1.5 pr-8 pl-3 text-sm font-medium text-slate-700 shadow-xs outline-none focus:border-brand focus:ring-4 focus:ring-brand/15"
        (change)="pick($any($event.target).value)"
      >
        @for (s of sessions(); track param(s)) {
          <option [value]="param(s)" [selected]="param(s) === current()">{{ label(s) }}</option>
        }
      </select>
    }
    <div
      class="inline-flex rounded-lg bg-slate-200/70 p-1 text-xs font-medium"
      role="group"
      aria-label="Programme"
    >
      @for (p of pathways; track p) {
        <button
          type="button"
          class="rounded-md px-3 py-1.5 transition"
          [class]="
            pathway() === p ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
          "
          [attr.aria-pressed]="pathway() === p"
          (click)="pathwayChange.emit(p)"
        >
          {{ names[p] }}
        </button>
      }
    </div>
  `,
})
export class AnalysisToolbar {
  readonly sessions = input.required<ExamSession[]>();
  readonly session = input.required<ExamSession | null>();
  readonly pathway = input.required<Pathway>();
  readonly sessionChange = output<ExamSession>();
  readonly pathwayChange = output<Pathway>();

  protected readonly pathways: Pathway[] = ['combined', 'dp', 'cp'];
  protected readonly names = PATHWAY_LABELS;
  protected readonly label = sessionLabel;
  protected readonly param = sessionParam;

  protected current(): string {
    const session = this.session();
    return session ? sessionParam(session) : '';
  }

  protected pick(value: string): void {
    const session = parseSessionParam(value);
    if (session) this.sessionChange.emit(session);
  }
}
