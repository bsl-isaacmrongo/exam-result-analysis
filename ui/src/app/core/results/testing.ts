import {
  Analysis,
  AnalysisResponse,
  PathwaySummary,
  StudentResult,
  SubjectStats,
  VaSummary,
} from './results.models';

/** Small, consistent analysis payloads for unit tests. */

const va = (entries: number, average_grade: number | null, average_va: number | null): VaSummary => ({
  entries,
  average_grade,
  average_va,
  va_entries: average_va === null ? 0 : entries,
});

function stats(
  entries: number,
  uptake: number,
  counts: number[],
  averageVa: number | null,
  male: number | null,
  female: number | null,
): SubjectStats {
  const average = counts.reduce((sum, n, i) => sum + n * (i + 1), 0) / entries;
  return {
    ...va(entries, average, averageVa),
    uptake,
    grade_counts: counts,
    male: va(1, average, male),
    female: va(1, average, female),
  };
}

function summary(over: Partial<PathwaySummary>): PathwaySummary {
  return {
    candidates: 2,
    matched: 2,
    average_points: 30,
    highest_points: 38,
    lowest_points: 22,
    average_grade: 5,
    average_va: -0.25,
    va_entries: 4,
    grade_counts: [0, 0, 1, 1, 2, 1, 1],
    gender: {
      M: { candidates: 1, ...va(3, 4.5, -0.5) },
      F: { candidates: 1, ...va(3, 5.5, 0.25) },
    },
    ...over,
  };
}

function student(over: Partial<StudentResult>): StudentResult {
  return {
    name: 'Student',
    school: 'bge',
    pathway: 'DP',
    gender: 'F',
    baseline: 110,
    cem_name: 'Student',
    match: 'confident',
    subjects: [],
    other_entries: [],
    ee_subject: null,
    ee_grade: null,
    tok_grade: null,
    rp_grade: null,
    btec_result: null,
    notes: null,
    core_points: null,
    subject_points: null,
    total_points: null,
    points: null,
    average_grade: null,
    average_va: null,
    awarded: true,
    failing: [],
    unchecked: [],
    checks: [],
    in_cohort: true,
    ...over,
  };
}

export function sampleAnalysis(): Analysis {
  return {
    summary: {
      dp: summary({
        diploma: {
          awarded: 1,
          rate: 50,
          average_points_awarded: 38,
          at_least_40: 0,
          at_least_40_rate: 0,
          above_35: 1,
          above_35_rate: 50,
        },
      }),
      cp: summary({
        candidates: 1,
        average_points: 12,
        average_va: null,
        va_entries: 0,
        certificate: { awarded: 1, rate: 100 },
      }),
      combined: summary({ candidates: 3 }),
    },
    subjects: [
      {
        key: 'eng-hl',
        label: 'Eng HL',
        subject: 'eng',
        subject_name: 'English A',
        level: 'HL',
        variant: null,
        group: 1,
        stats: {
          dp: stats(2, 100, [0, 0, 0, 1, 0, 1, 0], -0.5, -1, 0),
          cp: stats(1, 100, [0, 0, 0, 0, 1, 0, 0], 0, null, 0),
          combined: stats(3, 100, [0, 0, 0, 1, 1, 1, 0], -0.33, -1, 0),
        },
      },
      {
        key: 'mat-sl-aa',
        label: 'Mat SL AA',
        subject: 'mat',
        subject_name: 'Mathematics',
        level: 'SL',
        variant: 'aa',
        group: 5,
        stats: {
          dp: stats(1, 50, [0, 0, 0, 0, 0, 0, 1], 1.5, null, 1.5),
          cp: null,
          combined: stats(1, 33.3, [0, 0, 0, 0, 0, 0, 1], 1.5, null, 1.5),
        },
      },
    ],
    families: [
      {
        subject: 'eng',
        name: 'English A',
        short: 'Eng',
        stats: { dp: va(2, 5, -0.5), cp: va(1, 5, 0), combined: va(3, 5, -0.33) },
      },
    ],
    baseline_bands: [
      { band: '100–109', stats: { dp: { candidates: 1, ...va(3, 5, -0.5) }, cp: { candidates: 0, ...va(0, null, null) }, combined: { candidates: 1, ...va(3, 5, -0.5) } } },
    ],
    scatter: [
      { name: 'Ada Lovelace', pathway: 'DP', baseline: 120, points: 38, average_grade: 6, average_va: 0.5 },
      { name: 'Ben Okoth', pathway: 'DP', baseline: 95, points: 22, average_grade: 4, average_va: -1 },
      { name: 'Cleo Wanjiru', pathway: 'CP', baseline: 90, points: 12, average_grade: 4, average_va: 0 },
    ],
    trend: { dp: { slope: 0.64, intercept: -38.8, r2: 1, n: 2 }, cp: null },
    students: [
      student({
        name: 'Ada Lovelace',
        total_points: 38,
        points: 38,
        ee_grade: 'A',
        tok_grade: 'B',
        core_points: 3,
        average_grade: 6,
        average_va: 0.5,
        subjects: [
          { key: 'eng-hl', label: 'Eng HL', subject: 'eng', level: 'HL', variant: null, grade: 6, predicted: 6, va: 0 },
          { key: 'mat-sl-aa', label: 'Mat SL AA', subject: 'mat', level: 'SL', variant: 'aa', grade: 7, predicted: 5.5, va: 1.5 },
        ],
        unchecked: ['CAS'],
      }),
      student({
        name: 'Ben Okoth',
        gender: 'M',
        baseline: 95,
        total_points: 22,
        points: 22,
        awarded: false,
        failing: [
          { code: 'D1', message: 'Total 22 is below 24' },
          { code: 'D2', message: 'HL points 10 are below 12' },
        ],
      }),
      student({
        name: 'Cleo Wanjiru',
        pathway: 'CP',
        cem_name: 'Wanjiru Cleo',
        match: 'review',
        btec_result: 'D D M',
        points: 12,
      }),
    ],
    matching: {
      matched: 3,
      review: [{ name: 'Cleo Wanjiru', cem_name: 'Wanjiru Cleo' }],
      unmatched_results: ['Dan Mwangi'],
      unmatched_cem: [],
    },
    va_threshold: 1,
  };
}

export function sampleResponse(over: Partial<AnalysisResponse> = {}): AnalysisResponse {
  return {
    school: 'bge',
    sessions: [
      { year: 2026, session: 'may' },
      { year: 2025, session: 'may' },
    ],
    session: { year: 2026, session: 'may' },
    sources: {
      cem: [{ filename: 'CEM.xlsx', created_at: '2026-11-05T10:00:00Z' }],
      ib_results: [{ filename: 'IB.xlsx', created_at: '2026-11-05T10:00:00Z' }],
    },
    analysis: sampleAnalysis(),
    ...over,
  };
}
