import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';

import { Icon } from '../../../shared/ui/icon';
import {
  SAMPLE_GRADES,
  SAMPLE_KPIS,
  SAMPLE_SESSION,
  SAMPLE_SUBJECTS,
  SAMPLE_TREND,
  SubjectRow,
} from './sample-data';

type LevelFilter = 'all' | 'HL' | 'SL';

const LINE = { width: 560, height: 220, left: 36, right: 24, top: 28, bottom: 28 };
const BARS = { width: 420, height: 220, left: 36, right: 8, top: 24, bottom: 28 };

@Component({
  selector: 'app-overview',
  imports: [DecimalPipe, Icon],
  templateUrl: './overview.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Overview {
  protected readonly session = SAMPLE_SESSION;
  protected readonly kpis = SAMPLE_KPIS;
  protected readonly levels: LevelFilter[] = ['all', 'HL', 'SL'];
  protected readonly level = signal<LevelFilter>('all');

  protected readonly subjects = computed(() =>
    SAMPLE_SUBJECTS.filter((s) => this.level() === 'all' || s.level === this.level()),
  );

  protected readonly flagged = SAMPLE_SUBJECTS.find((s) => s.flagged);

  // --- Line chart: average diploma score by year -----------------------------
  protected readonly line = LINE;
  private readonly lineMin = 28;
  private readonly lineMax = 38;
  protected readonly lineTicks = [30, 34, 38];

  protected readonly trend = SAMPLE_TREND.years.map((year, i) => ({
    year,
    x: this.lineX(i),
    school: SAMPLE_TREND.school[i],
    schoolY: this.lineY(SAMPLE_TREND.school[i]),
    global: SAMPLE_TREND.global[i],
    globalY: this.lineY(SAMPLE_TREND.global[i]),
  }));
  protected readonly schoolPath = this.trend.map((p) => `${p.x},${p.schoolY}`).join(' ');
  protected readonly globalPath = this.trend.map((p) => `${p.x},${p.globalY}`).join(' ');

  private readonly firstGap = SAMPLE_TREND.school[0] - SAMPLE_TREND.global[0];
  private readonly lastGap = SAMPLE_TREND.school.at(-1)! - SAMPLE_TREND.global.at(-1)!;
  protected readonly gapSummary = {
    first: this.firstGap,
    last: this.lastGap,
    widened: this.lastGap > this.firstGap,
    fromYear: SAMPLE_TREND.years[0],
  };

  // --- Bar chart: grade distribution ----------------------------------------
  protected readonly bars = BARS;
  private readonly barMax = 40;
  protected readonly barTicks = [0, 20, 40];
  protected readonly grades = SAMPLE_GRADES.school.map((school, i) => {
    const slot = (BARS.width - BARS.left - BARS.right) / 7;
    const barWidth = Math.min(16, slot / 2.6);
    const centre = BARS.left + slot * i + slot / 2;
    const global = SAMPLE_GRADES.global[i];
    return {
      grade: i + 1,
      centre,
      barWidth,
      school,
      global,
      schoolX: centre - barWidth - 1,
      globalX: centre + 1,
      schoolY: this.barY(school),
      globalY: this.barY(global),
      highlight: i >= 4,
    };
  });
  protected readonly topGradeShare = {
    school: SAMPLE_GRADES.school[5] + SAMPLE_GRADES.school[6],
    global: SAMPLE_GRADES.global[5] + SAMPLE_GRADES.global[6],
  };

  protected gap(row: SubjectRow): number {
    return row.schoolAvg - row.globalAvg;
  }

  protected yearOnYear(row: SubjectRow): number {
    return row.trend.at(-1)! - row.trend.at(-2)!;
  }

  /** Polyline points for a 72×24 sparkline. */
  protected sparkline(values: number[]): string {
    const min = Math.min(...values);
    const range = Math.max(...values) - min || 1;
    return values
      .map((v, i) => `${(i / (values.length - 1)) * 70 + 1},${22 - ((v - min) / range) * 20}`)
      .join(' ');
  }

  protected barY(value: number): number {
    const plot = BARS.height - BARS.top - BARS.bottom;
    return BARS.height - BARS.bottom - (value / this.barMax) * plot;
  }

  protected lineY(value: number): number {
    const plot = LINE.height - LINE.top - LINE.bottom;
    return (
      LINE.height - LINE.bottom - ((value - this.lineMin) / (this.lineMax - this.lineMin)) * plot
    );
  }

  private lineX(index: number): number {
    const plot = LINE.width - LINE.left - LINE.right;
    return LINE.left + (index / (SAMPLE_TREND.years.length - 1)) * plot;
  }
}
