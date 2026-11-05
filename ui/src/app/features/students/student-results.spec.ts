import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { ResultsService } from '../../core/results/results.service';
import { sampleResponse } from '../../core/results/testing';
import { StudentResults } from './student-results';

describe('StudentResults', () => {
  async function render(url = '/ib/bge/students') {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'ib/:school/students', component: StudentResults }]),
        { provide: ResultsService, useValue: { analysis: vi.fn().mockResolvedValue(sampleResponse()) } },
      ],
    });
    const harness = await RouterTestingHarness.create(url);
    await harness.fixture.whenStable();
    return { harness, el: harness.routeNativeElement! };
  }

  const names = (el: HTMLElement) =>
    [...el.querySelectorAll('tbody > tr > th')].map((th) =>
      th.textContent?.replace('Review', '').trim(),
    );
  const button = (el: HTMLElement, text: string) =>
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;

  it('lists students with award status', async () => {
    const { el } = await render();
    expect(names(el)).toEqual(['Ada Lovelace', 'Ben Okoth', 'Cleo Wanjiru']);
    expect(el.textContent).toContain('Not awarded · D1, D2');
    expect(el.textContent).toContain('3 of 3 students shown');
  });

  it('filters by programme, status and name', async () => {
    const { harness, el } = await render('/ib/bge/students?pathway=cp');
    expect(names(el)).toEqual(['Cleo Wanjiru']);

    button(el, 'Combined').click();
    await harness.fixture.whenStable();
    button(el, 'Not awarded').click();
    await harness.fixture.whenStable();
    expect(names(el)).toEqual(['Ben Okoth']);

    button(el, 'Needs review').click();
    await harness.fixture.whenStable();
    expect(names(el)).toEqual(['Cleo Wanjiru']);

    button(el, 'All students').click();
    const search = el.querySelector<HTMLInputElement>('#student-search')!;
    search.value = 'ada';
    search.dispatchEvent(new Event('input'));
    await harness.fixture.whenStable();
    expect(names(el)).toEqual(['Ada Lovelace']);
  });

  it('expands a student to show subject VA', async () => {
    const { harness, el } = await render();
    const toggle = el.querySelector<HTMLButtonElement>('tbody th button')!;
    toggle.click();
    await harness.fixture.whenStable();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    const detail = el.querySelector('tbody table')!;
    expect(detail.textContent).toContain('Mat SL AA');
    expect(detail.textContent).toContain('+1.50');
    expect(el.textContent).toContain('Not in imported data');
  });
});
