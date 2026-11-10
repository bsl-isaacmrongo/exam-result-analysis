import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { injectAnalysis } from '../../../core/results/analysis-state';
import { AnalysisToolbar } from '../../../core/results/analysis-toolbar';
import {
  Analysis,
  PATHWAY_LABELS,
  Pathway,
  SubjectRow,
  sessionLabel,
} from '../../../core/results/results.models';
import { Chart } from '../../../shared/charts/chart';
import {
  bandVaOption,
  familyVaOption,
  genderVaOption,
  gradeShareOption,
  scatterOption,
  subjectGradeMixOption,
  subjectVaOption,
  uptakeOption,
} from '../../../shared/charts/chart-options';
import { Icon } from '../../../shared/ui/icon';
import { formatVa, vaTone } from '../../../shared/ui/va';

type LevelFilter = 'all' | 'HL' | 'SL';

export interface Kpi {
  label: string;
  value: string;
  suffix?: string;
  note: string;
  tone?: 'positive' | 'negative' | 'neutral';
  /** Students behind the figure, listed on demand so they can be celebrated. */
  roll?: { title: string; students: { name: string; points: number }[] };
}

function fixed(value: number | null | undefined, digits = 1): string {
  return value == null ? '–' : value.toFixed(digits);
}

/** Headline figures for the cohort summary (FR-7.1). */
export function buildKpis(analysis: Analysis, pathway: Pathway): Kpi[] {
  const s = analysis.summary[pathway];
  const va: Kpi = {
    label: 'Average subject VA',
    value: formatVa(s.average_va),
    note: s.va_entries
      ? `${s.va_entries} subject results compared with CEM predictions`
      : 'Import the CEM baseline to see value added',
    tone: vaTone(s.average_va, analysis.va_threshold / 2),
  };
  const range = s.lowest_points == null ? '' : ` · range ${s.lowest_points}–${s.highest_points}`;

  if (pathway === 'dp' && s.diploma) {
    const d = s.diploma;
    const topScorers = analysis.students
      .filter((st) => st.in_cohort && st.pathway === 'DP' && (st.total_points ?? 0) >= 40)
      .map((st) => ({ name: st.name, points: st.total_points! }))
      .sort((a, b) => b.points - a.points || a.name.localeCompare(b.name));
    return [
      {
        label: 'Diploma pass rate',
        value: `${fixed(d.rate)}%`,
        note: `${d.awarded} of ${s.candidates} candidates awarded the Diploma`,
      },
      {
        label: 'Average diploma points',
        value: fixed(s.average_points),
        suffix: '/ 45',
        note: `${fixed(d.average_points_awarded)} for Diploma holders${range}`,
      },
      {
        label: 'Scoring over 35 points',
        value: `${fixed(d.above_35_rate)}%`,
        note: `${d.above_35} candidates · ${d.at_least_40} with 40 points and above (${fixed(d.at_least_40_rate)}%)`,
        roll: topScorers.length ? { title: '40 points and above', students: topScorers } : undefined,
      },
      va,
    ];
  }
  if (pathway === 'cp' && s.certificate) {
    return [
      {
        label: 'Certificate rate',
        value: `${fixed(s.certificate.rate)}%`,
        note: `${s.certificate.awarded} of ${s.candidates} meet the conditions in the imported data`,
      },
      {
        label: 'Average DP course points',
        value: fixed(s.average_points),
        note: `Sum of each student's DP course grades${range}`,
      },
      {
        label: 'Average DP course grade',
        value: fixed(s.average_grade, 2),
        suffix: '/ 7',
        note: `Across ${s.grade_counts.reduce((a, b) => a + b, 0)} course results`,
      },
      va,
    ];
  }
  const grades = s.grade_counts.reduce((a, b) => a + b, 0);
  const top = grades ? ((s.grade_counts[5] + s.grade_counts[6]) / grades) * 100 : 0;
  return [
    {
      label: 'IB candidates',
      value: String(s.candidates),
      note: `${analysis.summary.dp.candidates} Diploma · ${analysis.summary.cp.candidates} Career-related`,
    },
    {
      label: 'Average subject grade',
      value: fixed(s.average_grade, 2),
      suffix: '/ 7',
      note: `${top.toFixed(1)}% of ${grades} subject grades were 6 or 7`,
    },
    {
      label: 'Average points per student',
      value: fixed(s.average_points),
      note: 'DP total points and CP course points together',
    },
    va,
  ];
}

/** Cohort summary, charts and subject matrix for one exam session. */
@Component({
  selector: 'app-overview',
  imports: [DecimalPipe, RouterLink, Icon, Chart, AnalysisToolbar],
  templateUrl: './overview.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Overview {
  protected readonly state = injectAnalysis();
  protected readonly analysis = this.state.analysis;
  protected readonly pathway = this.state.pathway;
  protected readonly pathwayNames = PATHWAY_LABELS;
  protected readonly sessionLabel = computed(() => sessionLabel(this.state.session()));
  protected readonly formatVa = formatVa;

  protected readonly levels: LevelFilter[] = ['all', 'HL', 'SL'];
  protected readonly level = signal<LevelFilter>('all');
  /** Label of the KPI card whose student list is expanded. */
  protected readonly openRoll = signal<string | null>(null);

  protected toggleRoll(label: string): void {
    this.openRoll.update((open) => (open === label ? null : label));
  }

  protected readonly hasCem = computed(() => !!this.state.response()?.sources.cem.length);
  protected readonly threshold = computed(() => this.analysis()?.va_threshold ?? 1);
  protected readonly summary = computed(() => this.analysis()?.summary[this.pathway()] ?? null);
  protected readonly kpis = computed(() => {
    const analysis = this.analysis();
    return analysis ? buildKpis(analysis, this.pathway()) : [];
  });
  protected readonly hasVa = computed(() => !!this.analysis()?.summary.combined.va_entries);

  protected readonly matchingIssues = computed(() => {
    const matching = this.analysis()?.matching;
    if (!matching || !this.hasCem()) return null;
    const count =
      matching.review.length + matching.unmatched_results.length + matching.unmatched_cem.length;
    return count ? matching : null;
  });

  /** Male vs female VA gap for the selected programme (FR-5.2). */
  protected readonly genderGap = computed(() => {
    const s = this.summary();
    if (!s) return null;
    const { M, F } = s.gender;
    if (M.average_va == null || F.average_va == null) return null;
    return { male: M, female: F, gap: Math.abs(F.average_va - M.average_va) };
  });

  // --- Charts ----------------------------------------------------------------
  protected readonly gradeShare = computed(() => {
    const a = this.analysis();
    return a ? gradeShareOption(a.summary) : null;
  });
  protected readonly uptake = computed(() => {
    const a = this.analysis();
    return a ? uptakeOption(a.subjects, this.pathway()) : null;
  });
  protected readonly gradeMix = computed(() => {
    const a = this.analysis();
    return a ? subjectGradeMixOption(a.subjects, this.pathway()) : null;
  });
  protected readonly subjectVa = computed(() => {
    const a = this.analysis();
    return a && this.hasVa() ? subjectVaOption(a.subjects, a.va_threshold) : null;
  });
  protected readonly genderVa = computed(() => {
    const a = this.analysis();
    return a && this.hasVa() ? genderVaOption(a.subjects, this.pathway(), a.va_threshold) : null;
  });
  protected readonly familyVa = computed(() => {
    const a = this.analysis();
    return a && this.hasVa() ? familyVaOption(a.families, a.va_threshold) : null;
  });
  protected readonly bandVa = computed(() => {
    const a = this.analysis();
    return a && this.hasVa()
      ? bandVaOption(a.baseline_bands, this.pathway(), a.va_threshold)
      : null;
  });
  /** CEM vs outcome per programme; DP and CP outcomes use different scales. */
  protected readonly scatters = computed(() => {
    const a = this.analysis();
    if (!a?.scatter.length) return [];
    const pathway = this.pathway();
    const wanted: ('dp' | 'cp')[] = pathway === 'combined' ? ['dp', 'cp'] : [pathway];
    return wanted
      .filter((p) => a.scatter.some((s) => s.pathway === p.toUpperCase()))
      .map((p) => ({
        pathway: p,
        title: p === 'dp' ? 'CEM baseline vs diploma points' : 'CEM baseline vs average DP grade',
        trend: a.trend[p],
        options: scatterOption(a.scatter, p, a.trend[p]),
      }));
  });

  // --- Subject matrix (FR-7.3) -----------------------------------------------
  protected readonly matrix = computed(() => {
    const a = this.analysis();
    if (!a) return [];
    const p = this.pathway();
    return a.subjects
      .filter((s) => s.stats[p] && (this.level() === 'all' || s.level === this.level()))
      .map((s) => ({ row: s, stats: s.stats[p]! }));
  });

  /** % of a subject's grades at `minGrade` or above (FR-4.1). */
  protected share(row: SubjectRow, minGrade: number): number {
    const stats = row.stats[this.pathway()]!;
    const count = stats.grade_counts.slice(minGrade - 1).reduce((a, b) => a + b, 0);
    return stats.entries ? (count / stats.entries) * 100 : 0;
  }

  protected vaClass(value: number | null | undefined): string {
    switch (vaTone(value, this.threshold())) {
      case 'positive':
        return 'text-emerald-700';
      case 'negative':
        return 'text-rose-700';
      default:
        return value == null ? 'text-slate-400' : 'text-slate-700';
    }
  }
}
