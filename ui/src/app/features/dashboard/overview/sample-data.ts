/**
 * Illustrative figures for the overview layout. Replace with API data once
 * results analysis endpoints exist; nothing here is real school data.
 */

export interface Kpi {
  label: string;
  value: string;
  suffix?: string;
  change: string;
  positive: boolean;
  comparison: string;
  note: string;
}

export interface SubjectRow {
  name: string;
  level: 'HL' | 'SL';
  entries: number;
  schoolAvg: number;
  globalAvg: number;
  /** Share of grades 6–7, percent. */
  topGrades: number;
  /** School average for the last five sessions, oldest first. */
  trend: number[];
  flagged?: boolean;
}

export const SAMPLE_SESSION = 'May 2025';

export const SAMPLE_KPIS: Kpi[] = [
  {
    label: 'Average diploma score',
    value: '35.4',
    suffix: '/ 45',
    change: '1.2 pts',
    positive: true,
    comparison: 'vs May 2024',
    note: 'Global reference 30.6 · +4.8 pts',
  },
  {
    label: 'Diploma pass rate',
    value: '95.8%',
    change: '1.5 pp',
    positive: true,
    comparison: 'vs May 2024',
    note: '92 of 96 candidates awarded diploma',
  },
  {
    label: 'Scoring 40+ points',
    value: '25.0%',
    change: '6.8 pp',
    positive: true,
    comparison: 'vs May 2024',
    note: '24 candidates · 3 achieved 45 points',
  },
  {
    label: 'Diploma candidates',
    value: '96',
    change: '8',
    positive: true,
    comparison: 'vs May 2024',
    note: '100% of cohort results included',
  },
];

export const SAMPLE_TREND = {
  years: [2021, 2022, 2023, 2024, 2025],
  school: [34.1, 33.6, 34.0, 34.2, 35.4],
  global: [31.0, 30.8, 30.2, 30.4, 30.6],
};

/** Share of subject grades 1–7, percent. */
export const SAMPLE_GRADES = {
  school: [1, 2, 5, 13, 28, 32, 19],
  global: [2, 6, 13, 24, 27, 20, 8],
};

export const SAMPLE_SUBJECTS: SubjectRow[] = [
  {
    name: 'English A: Language & Literature',
    level: 'HL',
    entries: 48,
    schoolAvg: 5.85,
    globalAvg: 5.12,
    topGrades: 62.5,
    trend: [5.4, 5.5, 5.58, 5.64, 5.85],
  },
  {
    name: 'Economics',
    level: 'HL',
    entries: 32,
    schoolAvg: 5.72,
    globalAvg: 5.04,
    topGrades: 59.4,
    trend: [5.2, 5.3, 5.31, 5.38, 5.72],
  },
  {
    name: 'Biology',
    level: 'HL',
    entries: 28,
    schoolAvg: 5.61,
    globalAvg: 4.78,
    topGrades: 53.6,
    trend: [5.1, 5.2, 5.3, 5.36, 5.61],
  },
  {
    name: 'Mathematics: Analysis & Approaches',
    level: 'HL',
    entries: 24,
    schoolAvg: 4.92,
    globalAvg: 4.85,
    topGrades: 33.3,
    trend: [5.3, 5.2, 5.12, 5.1, 4.92],
    flagged: true,
  },
  {
    name: 'French B',
    level: 'SL',
    entries: 38,
    schoolAvg: 5.78,
    globalAvg: 5.1,
    topGrades: 61.1,
    trend: [5.3, 5.38, 5.45, 5.5, 5.78],
  },
  {
    name: 'Chemistry',
    level: 'SL',
    entries: 22,
    schoolAvg: 5.27,
    globalAvg: 4.62,
    topGrades: 40.9,
    trend: [4.9, 5.0, 5.08, 5.15, 5.27],
  },
  {
    name: 'History',
    level: 'SL',
    entries: 30,
    schoolAvg: 5.4,
    globalAvg: 4.9,
    topGrades: 46.7,
    trend: [5.0, 5.1, 5.22, 5.3, 5.4],
  },
  {
    name: 'Physics',
    level: 'HL',
    entries: 18,
    schoolAvg: 5.06,
    globalAvg: 4.71,
    topGrades: 38.9,
    trend: [4.8, 4.86, 4.95, 5.0, 5.06],
  },
];
