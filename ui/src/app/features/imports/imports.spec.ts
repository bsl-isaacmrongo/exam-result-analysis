import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { AuthService } from '../../core/auth/auth.service';
import { ResultImport } from '../../core/results/results.models';
import { ResultsService } from '../../core/results/results.service';
import { Imports } from './imports';

const RESULTS: ResultImport = {
  id: 1,
  school: 'bge',
  kind: 'ib_results',
  year: 2026,
  session: 'may',
  filename: 'IB Results 2026.xlsx',
  summary: { dp_candidates: 32, cp_candidates: 22, subject_results: 251, warnings: ['Check Che'] },
  uploaded_by: 'Admin',
  created_at: '2026-11-05T10:00:00Z',
};

describe('Imports', () => {
  let service: { listImports: ReturnType<typeof vi.fn>; upload: ReturnType<typeof vi.fn>; remove: ReturnType<typeof vi.fn> };

  async function render(role: string, school = 'bge', imports: ResultImport[] = [RESULTS]) {
    service = {
      listImports: vi.fn().mockResolvedValue(imports),
      upload: vi.fn(),
      remove: vi.fn().mockResolvedValue(undefined),
    };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'ib/:school/imports', component: Imports }]),
        { provide: ResultsService, useValue: service },
        { provide: AuthService, useValue: { user: signal({ id: 1, email: 'a@b.c', name: null, role }) } },
      ],
    });
    const harness = await RouterTestingHarness.create(`/ib/${school}/imports`);
    await harness.fixture.whenStable();
    return { harness, el: harness.routeNativeElement! };
  }

  const button = (el: HTMLElement, text: string) =>
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;

  function choose(el: HTMLElement, file: File) {
    const input = el.querySelector<HTMLInputElement>('input[type=file]')!;
    Object.defineProperty(input, 'files', { value: { item: () => file }, configurable: true });
    input.dispatchEvent(new Event('change'));
  }

  it('lists imports by session and what is missing', async () => {
    const { el } = await render('user');
    expect(service.listImports).toHaveBeenCalledWith('bge');
    const items = [...el.querySelectorAll('li')].map((li) => li.textContent?.replace(/\s+/g, ' '));
    expect(items[0]).toMatch(/CEM baseline\s*Not imported/);
    expect(items[1]).toContain('IB Results 2026.xlsx · 32 DP · 22 CP · 251 grades');
    expect(el.querySelector('form')).toBeNull();
    expect(el.textContent).toContain('Only administrators can import data.');
  });

  it('uploads a file and shows the summary', async () => {
    const { harness, el } = await render('admin', 'bge', []);
    const created = { ...RESULTS, id: 2, kind: 'cem' as const, filename: 'CEM.xlsx', summary: { students: 52, predictions: 230, warnings: [] } };
    service.upload.mockResolvedValue(created);

    // Radios are CEM baseline, then IB results.
    el.querySelectorAll<HTMLInputElement>('input[type=radio]')[0].click();
    choose(el, new File(['x'], 'CEM.xlsx'));
    await harness.fixture.whenStable();
    expect(el.textContent).toContain('CEM.xlsx');
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    await harness.fixture.whenStable();

    expect(service.upload).toHaveBeenCalledWith(
      expect.objectContaining({ school: 'bge', kind: 'cem', file: expect.any(File) }),
    );
    expect(el.querySelector('[role=status]')?.textContent).toContain('52 students · 230 predictions');
    expect(el.querySelector('a[href^="/ib/bge/overview?session="]')).not.toBeNull();
  });

  it('shows workbook errors from the API', async () => {
    const { harness, el } = await render('admin', 'bge', []);
    service.upload.mockRejectedValue(
      new HttpErrorResponse({
        status: 422,
        error: { detail: { message: '1 value(s) need fixing.', errors: ['IBDP row 4: Eng grade 9'] } },
      }),
    );
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    await harness.fixture.whenStable();
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Choose an Excel file');

    choose(el, new File(['x'], 'bad.xlsx'));
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    await harness.fixture.whenStable();
    const alert = el.querySelector('[role=alert]')!;
    expect(alert.textContent).toContain('1 value(s) need fixing.');
    expect(alert.textContent).toContain('IBDP row 4: Eng grade 9');
  });

  it('asks for confirmation before deleting', async () => {
    const { harness, el } = await render('admin');
    button(el, 'Delete').click();
    await harness.fixture.whenStable();
    expect(service.remove).not.toHaveBeenCalled();
    button(el, 'Confirm delete').click();
    await harness.fixture.whenStable();
    expect(service.remove).toHaveBeenCalledWith(1);
    expect(el.textContent).toContain('Nothing imported yet');
  });

  it('has no import form for all schools', async () => {
    const { el } = await render('admin', 'all');
    expect(el.querySelector('form')).toBeNull();
    expect(el.textContent).toContain('Switch to a single school');
  });
});
