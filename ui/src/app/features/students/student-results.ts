import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { injectAnalysis } from '../../core/results/analysis-state';
import { AnalysisToolbar } from '../../core/results/analysis-toolbar';
import { PATHWAY_LABELS, StudentResult, sessionLabel } from '../../core/results/results.models';
import { Icon } from '../../shared/ui/icon';
import { formatVa, vaTone } from '../../shared/ui/va';

type StatusFilter = 'all' | 'not-awarded' | 'review';

/** Per-student award status, failing conditions and subject VA (FR-2, FR-3). */
@Component({
  selector: 'app-student-results',
  imports: [DecimalPipe, RouterLink, Icon, AnalysisToolbar],
  templateUrl: './student-results.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StudentResults {
  protected readonly state = injectAnalysis();
  protected readonly analysis = this.state.analysis;
  protected readonly pathway = this.state.pathway;
  protected readonly pathwayNames = PATHWAY_LABELS;
  protected readonly sessionLabel = computed(() => sessionLabel(this.state.session()));
  protected readonly formatVa = formatVa;

  protected readonly query = signal('');
  protected readonly status = signal<StatusFilter>('all');
  protected readonly expanded = signal<ReadonlySet<string>>(new Set());
  protected readonly filters: { value: StatusFilter; label: string }[] = [
    { value: 'all', label: 'All students' },
    { value: 'not-awarded', label: 'Not awarded' },
    { value: 'review', label: 'Needs review' },
  ];

  protected readonly students = computed(() => {
    const analysis = this.analysis();
    if (!analysis) return [];
    const pathway = this.pathway();
    const words = this.query().toLowerCase().split(/\s+/).filter(Boolean);
    return analysis.students.filter((s) => {
      if (pathway !== 'combined' && s.pathway !== pathway.toUpperCase()) return false;
      if (this.status() === 'not-awarded' && s.awarded !== false) return false;
      if (this.status() === 'review' && !this.needsReview(s)) return false;
      const name = s.name.toLowerCase();
      return words.every((w) => name.includes(w));
    });
  });

  protected key(student: StudentResult): string {
    return `${student.school}:${student.pathway}:${student.name}`;
  }

  protected toggle(student: StudentResult): void {
    const key = this.key(student);
    this.expanded.update((set) => {
      const next = new Set(set);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  }

  protected isExpanded(student: StudentResult): boolean {
    return this.expanded().has(this.key(student));
  }

  protected failingCodes(student: StudentResult): string {
    return [...new Set(student.failing.map((f) => f.code))].join(', ');
  }

  protected failingSummary(student: StudentResult): string {
    return student.failing.map((f) => `${f.code}: ${f.message}`).join('\n');
  }

  /** Unmatched / surname-only CEM match, or values that disagree with the file. */
  protected needsReview(s: StudentResult): boolean {
    const hasCem = !!this.state.response()?.sources.cem.length;
    return (hasCem && s.match !== 'confident') || s.checks.length > 0;
  }

  protected vaClass(value: number | null | undefined): string {
    const tone = vaTone(value, this.analysis()?.va_threshold ?? 1);
    if (tone === 'positive') return 'text-emerald-700';
    if (tone === 'negative') return 'text-rose-700';
    return value == null ? 'text-slate-400' : 'text-slate-700';
  }
}
