import { sampleAnalysis } from '../../core/results/testing';
import {
  bandVaOption,
  familyVaOption,
  genderVaOption,
  gradeShareOption,
  scatterOption,
  subjectGradeMixOption,
  subjectVaOption,
  uptakeOption,
} from './chart-options';

type Series = { name?: string; data: unknown[] };
const series = (option: object) => (option as { series: Series[] }).series;
const categories = (option: object) => (option as { xAxis: { data: string[] } }).xAxis.data;

describe('chart options', () => {
  const analysis = sampleAnalysis();

  it('shows the share of grades 7 to 1 per programme', () => {
    const option = gradeShareOption(analysis.summary);
    expect(categories(option)).toEqual(['7', '6', '5', '4', '3', '2', '1']);
    expect(series(option).map((s) => s.name)).toEqual(['Combined', 'DP', 'CP']);
    // grade_counts [0,0,1,1,2,1,1] of 6 grades.
    expect(series(option)[0].data).toEqual([16.7, 16.7, 33.3, 16.7, 16.7, 0, 0]);
  });

  it('limits uptake and grade mix to subjects taken in the programme', () => {
    expect(categories(uptakeOption(analysis.subjects, 'cp'))).toEqual(['Eng HL']);
    expect(series(uptakeOption(analysis.subjects, 'dp'))[0].data).toEqual([100, 50]);
    const mix = subjectGradeMixOption(analysis.subjects, 'dp');
    expect(series(mix).map((s) => s.name)).toEqual(['7', '6', '5', '4', '3', '2', '1']);
    // Eng HL DP: one 4 and one 6 → 50% each.
    expect(series(mix)[1].data[0]).toBe(50);
    expect(series(mix)[3].data[0]).toBe(50);
  });

  it('plots VA by subject, gender, family and band', () => {
    const bySubject = subjectVaOption(analysis.subjects, 1);
    expect(series(bySubject).map((s) => s.data)).toEqual([
      [-0.5, 1.5],
      [0, null],
      [-0.33, 1.5],
    ]);
    const byGender = genderVaOption(analysis.subjects, 'dp', 1);
    expect(series(byGender).map((s) => s.name)).toEqual(['Male', 'Female']);
    expect(series(byGender)[0].data).toEqual([-1, null]);
    expect(categories(familyVaOption(analysis.families, 1))).toEqual(['Eng']);
    expect(series(bandVaOption(analysis.baseline_bands, 'dp', 1))[0].data).toEqual([-0.5]);
  });

  it('draws the scatter with a trendline for one programme', () => {
    const option = scatterOption(analysis.scatter, 'dp', analysis.trend.dp);
    const [points, trend] = series(option);
    expect(points.data).toEqual([
      { value: [120, 38], name: 'Ada Lovelace' },
      { value: [95, 22], name: 'Ben Okoth' },
    ]);
    expect(trend.data).toEqual([
      [95, 22],
      [120, 38],
    ]);
    const cp = scatterOption(analysis.scatter, 'cp', null);
    expect(series(cp)).toHaveLength(1);
    expect(series(cp)[0].data).toEqual([{ value: [90, 4], name: 'Cleo Wanjiru' }]);
  });
});
