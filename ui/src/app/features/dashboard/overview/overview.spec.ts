import { Component, input } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { ResultsService } from '../../../core/results/results.service';
import { sampleAnalysis, sampleResponse } from '../../../core/results/testing';
import { AnalysisResponse } from '../../../core/results/results.models';
import { Chart } from '../../../shared/charts/chart';
import { Overview, buildKpis } from './overview';

@Component({ selector: 'app-chart', template: '<div data-chart [attr.aria-label]="label()"></div>' })
class ChartStub {
  readonly options = input<unknown>();
  readonly label = input('');
  readonly height = input('');
}

describe('buildKpis', () => {
  it('summarises the diploma programme', () => {
    const kpis = buildKpis(sampleAnalysis(), 'dp');
    expect(kpis.map((k) => [k.label, k.value])).toEqual([
      ['Diploma pass rate', '50.0%'],
      ['Average diploma points', '30.0'],
      ['Scoring over 35 points', '50.0%'],
      ['Average subject VA', '−0.25'],
    ]);
    expect(kpis[0].note).toBe('1 of 2 candidates awarded the Diploma');
    expect(kpis[2].roll).toBeUndefined();
  });

  it('lists DP students with 40 points and above, highest first', () => {
    const analysis = sampleAnalysis();
    analysis.students[0].total_points = 40;
    analysis.students[1].total_points = 43;
    const kpis = buildKpis(analysis, 'dp');
    expect(kpis[2].roll).toEqual({
      title: '40 points and above',
      students: [
        { name: 'Ben Okoth', points: 43 },
        { name: 'Ada Lovelace', points: 40 },
      ],
    });
  });

  it('explains missing VA for the career-related programme', () => {
    const kpis = buildKpis(sampleAnalysis(), 'cp');
    expect(kpis[0]).toMatchObject({ label: 'Certificate rate', value: '100.0%' });
    expect(kpis[3]).toMatchObject({ value: '–', note: 'Import the CEM baseline to see value added' });
  });
});

describe('Overview', () => {
  let analysis: ReturnType<typeof vi.fn>;

  async function render(response: AnalysisResponse, url = '/ib/bge/overview') {
    analysis = vi.fn().mockResolvedValue(response);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'ib/:school/overview', component: Overview }]),
        { provide: ResultsService, useValue: { analysis } },
      ],
    });
    TestBed.overrideComponent(Overview, {
      remove: { imports: [Chart] },
      add: { imports: [ChartStub] },
    });
    const harness = await RouterTestingHarness.create(url);
    await harness.fixture.whenStable();
    return harness;
  }

  it('shows KPIs, charts and the subject matrix', async () => {
    const harness = await render(sampleResponse());
    const el = harness.routeNativeElement!;
    expect(analysis).toHaveBeenCalledWith('bge', null);
    expect(el.textContent?.replace(/\s+/g, ' ')).toContain('May 2026 session · Combined');
    expect([...el.querySelectorAll('article h2')].map((h) => h.textContent?.trim())).toContain(
      'Subject uptake',
    );
    expect(el.querySelectorAll('[data-chart]').length).toBeGreaterThanOrEqual(7);
    expect(
      [...el.querySelectorAll('tbody th')].map((th) => th.textContent?.replace(/\s+/g, ' ').trim()),
    ).toEqual(['Eng HL English A', 'Mat SL AA Mathematics']);
    expect(el.textContent).toContain('female students averaged');
  });

  it('switches programme and session through the query string', async () => {
    const harness = await render(sampleResponse());
    const el = harness.routeNativeElement!;
    const dp = [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Diploma (DP)')!;
    dp.click();
    await harness.fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/ib/bge/overview?pathway=dp');
    expect(el.textContent).toContain('Diploma pass rate');

    const select = el.querySelector<HTMLSelectElement>('#analysis-session')!;
    select.value = '2025-may';
    select.dispatchEvent(new Event('change'));
    await harness.fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/ib/bge/overview?pathway=dp&session=2025-may');
    expect(analysis).toHaveBeenLastCalledWith('bge', { year: 2025, session: 'may' });
  });

  it('flags students who could not be matched to CEM', async () => {
    const harness = await render(sampleResponse());
    const notice = harness.routeNativeElement!.querySelector('details')!;
    expect(notice.textContent).toContain('1 without a CEM record');
    expect(notice.textContent).toContain('Cleo Wanjiru → Wanjiru Cleo');
  });

  it('asks for the CEM baseline when only results are imported', async () => {
    const harness = await render(sampleResponse({ sources: { cem: [], ib_results: [] } }));
    const el = harness.routeNativeElement!;
    expect(el.textContent).toContain('Value added needs CEM predictions.');
    expect(el.querySelector('details')).toBeNull();
  });

  it('links to imports when there are no results', async () => {
    const harness = await render(sampleResponse({ sessions: [], session: null, analysis: null }));
    const el = harness.routeNativeElement!;
    expect(el.textContent).toContain('No IB results yet');
    expect(el.querySelector('a[href="/ib/bge/imports"]')).not.toBeNull();
  });
});
