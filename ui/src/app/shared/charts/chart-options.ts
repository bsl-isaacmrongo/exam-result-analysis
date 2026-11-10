import type { EChartsCoreOption } from 'echarts/core';

import {
  BaselineBand,
  Pathway,
  PathwaySummary,
  ScatterPoint,
  SubjectFamily,
  SubjectRow,
  Trend,
} from '../../core/results/results.models';

/** Series colours, in line with the brand palette in styles.css. */
export const COLOURS: Record<Pathway | 'male' | 'female', string> = {
  combined: '#f59e0b',
  dp: '#020381',
  cp: '#0693e3',
  male: '#0693e3',
  female: '#e11d48',
};

/** Grades 7 → 1, strongest first. */
export const GRADE_COLOURS: Record<number, string> = {
  7: '#020381',
  6: '#2563eb',
  5: '#0693e3',
  4: '#22c55e',
  3: '#f59e0b',
  2: '#f97316',
  1: '#dc2626',
};

const PATHWAY_NAMES: Record<Pathway, string> = { combined: 'Combined', dp: 'DP', cp: 'CP' };
const GRADES_DESC = [7, 6, 5, 4, 3, 2, 1];
const AXIS = { color: '#64748b', fontSize: 11 };
const SPLIT_LINE = { lineStyle: { color: '#f1f5f9' } };
const TOOLTIP = {
  backgroundColor: '#fff',
  borderColor: '#e2e8f0',
  textStyle: { color: '#0f172a', fontSize: 12 },
  extraCssText: 'box-shadow: 0 4px 12px rgb(15 23 42 / 0.08); border-radius: 8px;',
};
const LEGEND = { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: AXIS };

function base(): EChartsCoreOption {
  return { textStyle: { fontFamily: 'inherit' }, animationDuration: 400 };
}

function pct(part: number, whole: number): number {
  return whole ? Math.round((part / whole) * 1000) / 10 : 0;
}

function va(value: number | null | undefined): string {
  return value == null ? '–' : `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
}

/** Axis labels for many subjects: rotated, every label shown. */
function subjectAxis(labels: string[]) {
  return {
    type: 'category',
    data: labels,
    axisLabel: { ...AXIS, rotate: labels.length > 12 ? 45 : 0, interval: 0 },
    axisTick: { alignWithLabel: true },
    axisLine: { lineStyle: { color: '#cbd5e1' } },
  };
}

function grid(manyLabels: boolean) {
  return { left: 8, right: 8, top: 36, bottom: manyLabels ? 8 : 4, containLabel: true };
}

/** % of each grade, 7 → 1, one series per pathway (report: "% of each grade"). */
export function gradeShareOption(summary: Record<Pathway, PathwaySummary>): EChartsCoreOption {
  const pathways: Pathway[] = ['combined', 'dp', 'cp'];
  return {
    ...base(),
    color: pathways.map((p) => COLOURS[p]),
    legend: LEGEND,
    grid: grid(false),
    tooltip: { ...TOOLTIP, trigger: 'axis', valueFormatter: (v: number) => `${v}%` },
    xAxis: {
      type: 'category',
      data: GRADES_DESC.map(String),
      name: 'Grade',
      nameLocation: 'middle',
      nameGap: 26,
      nameTextStyle: AXIS,
      axisLabel: AXIS,
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: { type: 'value', axisLabel: { ...AXIS, formatter: '{value}%' }, splitLine: SPLIT_LINE },
    series: pathways.map((p) => {
      const counts = summary[p].grade_counts;
      const total = counts.reduce((a, b) => a + b, 0);
      return {
        name: PATHWAY_NAMES[p],
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: 'top', fontSize: 10, color: '#475569', formatter: '{c}%' },
        data: GRADES_DESC.map((g) => pct(counts[g - 1], total)),
      };
    }),
  };
}

/** % of the pathway's candidates taking each subject and level. */
export function uptakeOption(subjects: SubjectRow[], pathway: Pathway): EChartsCoreOption {
  const rows = subjects.filter((s) => s.stats[pathway]);
  return {
    ...base(),
    color: [COLOURS[pathway]],
    grid: grid(true),
    tooltip: {
      ...TOOLTIP,
      trigger: 'axis',
      formatter: (params: { dataIndex: number }[]) => {
        const row = rows[params[0].dataIndex];
        const stats = row.stats[pathway]!;
        return `<b>${row.label}</b> · ${row.subject_name}<br/>${stats.uptake}% (${stats.entries} students)`;
      },
    },
    xAxis: subjectAxis(rows.map((s) => s.label)),
    yAxis: { type: 'value', axisLabel: { ...AXIS, formatter: '{value}%' }, splitLine: SPLIT_LINE },
    series: [
      {
        type: 'bar',
        barMaxWidth: 24,
        itemStyle: { borderRadius: [3, 3, 0, 0] },
        label: { show: rows.length <= 40, position: 'top', fontSize: 9, color: '#475569', formatter: '{c}%' },
        data: rows.map((s) => s.stats[pathway]!.uptake),
      },
    ],
  };
}

/** Stacked share of grades 7 → 1 within each subject and level. */
export function subjectGradeMixOption(subjects: SubjectRow[], pathway: Pathway): EChartsCoreOption {
  const rows = subjects.filter((s) => s.stats[pathway]);
  return {
    ...base(),
    legend: { ...LEGEND, data: GRADES_DESC.map(String) },
    grid: grid(true),
    tooltip: {
      ...TOOLTIP,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: { dataIndex: number; seriesName: string; value: number; marker: string }[]) => {
        const row = rows[params[0].dataIndex];
        const lines = params
          .filter((p) => p.value > 0)
          .map((p) => `${p.marker} Grade ${p.seriesName}: ${p.value}%`);
        return `<b>${row.label}</b> (${row.stats[pathway]!.entries})<br/>${lines.join('<br/>')}`;
      },
    },
    xAxis: subjectAxis(rows.map((s) => s.label)),
    yAxis: { type: 'value', max: 100, axisLabel: { ...AXIS, formatter: '{value}%' }, splitLine: SPLIT_LINE },
    series: GRADES_DESC.map((g) => ({
      name: String(g),
      type: 'bar',
      stack: 'grades',
      barMaxWidth: 24,
      color: GRADE_COLOURS[g],
      data: rows.map((s) => {
        const stats = s.stats[pathway]!;
        return pct(stats.grade_counts[g - 1], stats.entries);
      }),
    })),
  };
}

function vaAxis(threshold: number) {
  return {
    type: 'value',
    axisLabel: AXIS,
    splitLine: SPLIT_LINE,
    min: (v: { min: number }) => Math.min(-threshold - 0.5, Math.floor(v.min * 2) / 2),
    max: (v: { max: number }) => Math.max(threshold + 0.5, Math.ceil(v.max * 2) / 2),
  };
}

function thresholdLines(threshold: number) {
  return {
    silent: true,
    symbol: 'none',
    label: { show: false },
    lineStyle: { type: 'dashed', color: '#94a3b8', width: 1 },
    data: [{ yAxis: threshold }, { yAxis: -threshold }],
  };
}

function vaTooltip(names: string[], counts: (series: number, index: number) => number) {
  return {
    ...TOOLTIP,
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params: { dataIndex: number; seriesIndex: number; seriesName: string; value: number | null; marker: string }[]) => {
      const lines = params
        .filter((p) => p.value != null)
        .map((p) => `${p.marker} ${p.seriesName}: <b>${va(p.value)}</b> (n=${counts(p.seriesIndex, p.dataIndex)})`);
      return `<b>${names[params[0].dataIndex]}</b><br/>${lines.join('<br/>') || 'No CEM predictions'}`;
    },
  };
}

/** Average VA per subject and level, one series per pathway. */
export function subjectVaOption(subjects: SubjectRow[], threshold: number): EChartsCoreOption {
  const pathways: Pathway[] = ['dp', 'cp', 'combined'];
  const rows = subjects.filter((s) => pathways.some((p) => s.stats[p]?.va_entries));
  return {
    ...base(),
    color: pathways.map((p) => COLOURS[p]),
    legend: LEGEND,
    grid: grid(true),
    tooltip: vaTooltip(
      rows.map((r) => `${r.label} · ${r.subject_name}`),
      (series, index) => rows[index].stats[pathways[series]]?.va_entries ?? 0,
    ),
    xAxis: subjectAxis(rows.map((s) => s.label)),
    yAxis: vaAxis(threshold),
    series: pathways.map((p, i) => ({
      name: PATHWAY_NAMES[p],
      type: 'bar',
      barMaxWidth: 10,
      barGap: '15%',
      data: rows.map((s) => s.stats[p]?.average_va ?? null),
      markLine: i === 0 ? thresholdLines(threshold) : undefined,
    })),
  };
}

/** Average VA by gender for each subject and level in one pathway. */
export function genderVaOption(subjects: SubjectRow[], pathway: Pathway, threshold: number): EChartsCoreOption {
  const rows = subjects.filter(
    (s) => s.stats[pathway]?.male.va_entries || s.stats[pathway]?.female.va_entries,
  );
  const genders = ['male', 'female'] as const;
  return {
    ...base(),
    color: [COLOURS.male, COLOURS.female],
    legend: LEGEND,
    grid: grid(true),
    tooltip: vaTooltip(
      rows.map((r) => r.label),
      (series, index) => rows[index].stats[pathway]![genders[series]].va_entries,
    ),
    xAxis: subjectAxis(rows.map((s) => s.label)),
    yAxis: vaAxis(threshold),
    series: genders.map((g, i) => ({
      name: g === 'male' ? 'Male' : 'Female',
      type: 'bar',
      barMaxWidth: 12,
      data: rows.map((s) => s.stats[pathway]![g].average_va),
      markLine: i === 0 ? thresholdLines(threshold) : undefined,
    })),
  };
}

/** Average VA per subject (all levels together), one series per pathway. */
export function familyVaOption(families: SubjectFamily[], threshold: number): EChartsCoreOption {
  const pathways: Pathway[] = ['combined', 'dp', 'cp'];
  const rows = families.filter((f) => pathways.some((p) => f.stats[p]?.va_entries));
  return {
    ...base(),
    color: pathways.map((p) => COLOURS[p]),
    legend: LEGEND,
    grid: grid(true),
    tooltip: vaTooltip(
      rows.map((r) => r.name),
      (series, index) => rows[index].stats[pathways[series]]?.va_entries ?? 0,
    ),
    xAxis: subjectAxis(rows.map((f) => f.short)),
    yAxis: vaAxis(threshold),
    series: pathways.map((p, i) => ({
      name: PATHWAY_NAMES[p],
      type: 'bar',
      barMaxWidth: 12,
      data: rows.map((f) => f.stats[p]?.average_va ?? null),
      markLine: i === 0 ? thresholdLines(threshold) : undefined,
    })),
  };
}

/** Average VA by CEM baseline band (residual matrix, FR-3.4). */
export function bandVaOption(bands: BaselineBand[], pathway: Pathway, threshold: number): EChartsCoreOption {
  return {
    ...base(),
    color: [COLOURS[pathway]],
    grid: grid(false),
    tooltip: {
      ...TOOLTIP,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: { dataIndex: number }[]) => {
        const band = bands[params[0].dataIndex];
        const stats = band.stats[pathway];
        return `<b>CEM ${band.band}</b><br/>Average VA <b>${va(stats.average_va)}</b><br/>` +
          `${stats.candidates} students · ${stats.va_entries} subject results`;
      },
    },
    xAxis: {
      type: 'category',
      data: bands.map((b) => b.band),
      name: 'CEM baseline score',
      nameLocation: 'middle',
      nameGap: 26,
      nameTextStyle: AXIS,
      axisLabel: AXIS,
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    yAxis: vaAxis(threshold),
    series: [
      {
        type: 'bar',
        barMaxWidth: 36,
        itemStyle: { borderRadius: 3 },
        label: {
          show: true,
          position: 'top',
          fontSize: 10,
          color: '#475569',
          formatter: (p: { dataIndex: number }) => `n=${bands[p.dataIndex].stats[pathway].candidates}`,
        },
        data: bands.map((b) => b.stats[pathway].average_va),
        markLine: thresholdLines(threshold),
      },
    ],
  };
}

/**
 * CEM baseline (x) against the IB outcome (y) with a least-squares trendline (FR-7.2):
 * total points for DP, average DP course grade for CP.
 */
export function scatterOption(points: ScatterPoint[], pathway: 'dp' | 'cp', trend: Trend | null): EChartsCoreOption {
  const dp = pathway === 'dp';
  const rows = points.filter((p) => p.pathway === pathway.toUpperCase());
  const y = (p: ScatterPoint) => (dp ? p.points : p.average_grade);
  const xs = rows.map((p) => p.baseline);
  const minX = Math.floor(Math.min(...xs) / 5) * 5;
  const maxX = Math.ceil(Math.max(...xs) / 5) * 5;
  const series: object[] = [
    {
      name: dp ? 'DP candidates' : 'CP candidates',
      type: 'scatter',
      symbolSize: 9,
      itemStyle: { color: COLOURS[pathway], opacity: 0.8 },
      data: rows.filter((p) => y(p) != null).map((p) => ({ value: [p.baseline, y(p)], name: p.name })),
    },
  ];
  if (trend && rows.length) {
    series.push({
      name: 'Trend',
      type: 'line',
      symbol: 'none',
      silent: true,
      lineStyle: { type: 'dashed', color: '#64748b', width: 1.5 },
      data: [minX, maxX].map((x) => [x, Math.round((trend.slope * x + trend.intercept) * 100) / 100]),
    });
  }
  return {
    ...base(),
    // Extra bottom space: containLabel reserves room for tick labels only, not the axis name.
    grid: { left: 8, right: 16, top: 16, bottom: 28, containLabel: true },
    tooltip: {
      ...TOOLTIP,
      trigger: 'item',
      formatter: (p: { seriesType: string; name: string; value: number[] }) =>
        p.seriesType === 'scatter'
          ? `<b>${p.name}</b><br/>CEM ${p.value[0]} · ${dp ? `${p.value[1]} points` : `average grade ${p.value[1]}`}`
          : '',
    },
    xAxis: {
      type: 'value',
      min: minX,
      max: maxX,
      name: 'CEM baseline score',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { ...AXIS, fontWeight: 600 },
      axisLabel: AXIS,
      splitLine: SPLIT_LINE,
    },
    yAxis: {
      type: 'value',
      min: dp ? (v: { min: number }) => Math.max(0, Math.floor(v.min / 5) * 5) : 1,
      max: dp ? 45 : 7,
      name: dp ? 'IB total points' : 'Average DP grade',
      nameTextStyle: AXIS,
      axisLabel: AXIS,
      splitLine: SPLIT_LINE,
    },
    series,
  };
}
