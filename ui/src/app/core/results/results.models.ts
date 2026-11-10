/** Types for `/api/imports` and `/api/analysis/ib`; see api/app/features/results. */

export type ImportKind = 'cem' | 'ib_results';
export type ExamSeries = 'may' | 'nov';
export type Pathway = 'dp' | 'cp' | 'combined';

export interface ImportSummary {
  warnings?: string[];
  /** Filename of the import this one replaced. */
  replaced?: string;
  students?: number;
  predictions?: number;
  dp_candidates?: number;
  cp_candidates?: number;
  subject_results?: number;
}

export interface ResultImport {
  id: number;
  school: string;
  kind: ImportKind;
  year: number;
  session: ExamSeries;
  filename: string;
  summary: ImportSummary;
  uploaded_by: string | null;
  created_at: string;
}

export interface NewImport {
  school: string;
  kind: ImportKind;
  year: number;
  session: ExamSeries;
  file: File;
}

export interface ExamSession {
  year: number;
  session: ExamSeries;
}

export interface VaSummary {
  entries: number;
  average_grade: number | null;
  average_va: number | null;
  va_entries: number;
}

export interface PathwaySummary {
  candidates: number;
  matched: number;
  /** DP: total diploma points; CP: sum of DP course grades. */
  average_points: number | null;
  highest_points: number | null;
  lowest_points: number | null;
  average_grade: number | null;
  average_va: number | null;
  va_entries: number;
  /** Count of grades 1–7 (index 0 = grade 1). */
  grade_counts: number[];
  gender: Record<'M' | 'F', VaSummary & { candidates: number }>;
  diploma?: {
    awarded: number;
    rate: number | null;
    average_points_awarded: number | null;
    at_least_40: number;
    at_least_40_rate: number | null;
    above_35: number;
    above_35_rate: number | null;
  };
  certificate?: { awarded: number; rate: number | null };
}

export interface SubjectStats extends VaSummary {
  /** % of the pathway's candidates taking this subject at this level. */
  uptake: number | null;
  grade_counts: number[];
  male: VaSummary;
  female: VaSummary;
}

export interface SubjectRow {
  key: string;
  /** e.g. "Eng HL", "Fre Ab", "Mat SL AI". */
  label: string;
  subject: string;
  subject_name: string;
  level: 'HL' | 'SL' | null;
  variant: string | null;
  group: number;
  stats: Record<Pathway, SubjectStats | null>;
}

export interface SubjectFamily {
  subject: string;
  name: string;
  short: string;
  stats: Record<Pathway, VaSummary | null>;
}

export interface BaselineBand {
  band: string;
  stats: Record<Pathway, VaSummary & { candidates: number }>;
}

export interface ScatterPoint {
  name: string;
  pathway: 'DP' | 'CP';
  baseline: number;
  points: number | null;
  average_grade: number | null;
  average_va: number | null;
}

export interface Trend {
  slope: number;
  intercept: number;
  r2: number | null;
  n: number;
}

export interface StudentSubject {
  key: string;
  label: string;
  subject: string;
  level: string | null;
  variant: string | null;
  grade: number;
  predicted: number | null;
  va: number | null;
}

export interface StudentResult {
  name: string;
  school: string;
  pathway: 'DP' | 'CP';
  gender: 'M' | 'F' | null;
  baseline: number | null;
  cem_name: string | null;
  match: 'confident' | 'review' | null;
  subjects: StudentSubject[];
  other_entries: string[];
  ee_subject: string | null;
  ee_grade: string | null;
  tok_grade: string | null;
  rp_grade: string | null;
  btec_result: string | null;
  notes: string | null;
  core_points: number | null;
  subject_points: number | null;
  total_points: number | null;
  points: number | null;
  average_grade: number | null;
  average_va: number | null;
  /** null when there are no DP course grades to judge (e.g. BTEC-only). */
  awarded: boolean | null;
  failing: { code: string; message: string }[];
  /** Conditions not in the imported data, e.g. CAS. */
  unchecked: string[];
  /** Differences between the file and the recalculated values. */
  checks: string[];
  in_cohort: boolean;
}

export interface Analysis {
  summary: Record<Pathway, PathwaySummary>;
  subjects: SubjectRow[];
  families: SubjectFamily[];
  baseline_bands: BaselineBand[];
  scatter: ScatterPoint[];
  trend: { dp: Trend | null; cp: Trend | null };
  students: StudentResult[];
  matching: {
    matched: number;
    review: { name: string; cem_name: string }[];
    unmatched_results: string[];
    unmatched_cem: string[];
  };
  va_threshold: number;
}

export interface AnalysisResponse {
  school: string;
  sessions: ExamSession[];
  session: ExamSession | null;
  sources: Record<ImportKind, { filename: string; created_at: string }[]>;
  analysis: Analysis | null;
}

export const IMPORT_KINDS: Record<ImportKind, { title: string; description: string }> = {
  cem: {
    title: 'CEM baseline',
    description: 'CEM IBE export: one row per student and subject with the predicted points.',
  },
  ib_results: {
    title: 'IB results',
    description: 'Final DP and CP results workbook (IBDP and IBCP sheets).',
  },
};

export const PATHWAY_LABELS: Record<Pathway, string> = {
  combined: 'Combined',
  dp: 'Diploma (DP)',
  cp: 'Career-related (CP)',
};

export function sessionLabel(session: ExamSession | null | undefined): string {
  if (!session) return '';
  return `${session.session === 'may' ? 'May' : 'November'} ${session.year}`;
}

/** Query-param form: `2026-may`. */
export function sessionParam(session: ExamSession): string {
  return `${session.year}-${session.session}`;
}

export function parseSessionParam(value: string | null | undefined): ExamSession | null {
  const match = /^(\d{4})-(may|nov)$/.exec(value ?? '');
  return match ? { year: Number(match[1]), session: match[2] as ExamSeries } : null;
}
