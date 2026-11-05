import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth/auth.service';
import { Settings } from './settings';

const API = 'http://localhost:8000/api/schools';
const BGE = { code: 'bge', name: 'Braeburn Garden Estate', curricula: ['ib'], is_active: true };

describe('Settings', () => {
  let fixture: ComponentFixture<Settings>;
  let http: HttpTestingController;
  let el: HTMLElement;

  async function setup(role: string) {
    TestBed.configureTestingModule({
      imports: [Settings],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: { user: signal({ id: 1, email: 'a@b.c', name: null, role }) },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Settings);
    el = fixture.nativeElement;
    http.expectOne(`${API}?include_inactive=true`).flush([BGE]);
    await fixture.whenStable();
  }

  const button = (text: string) =>
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === text)!;

  function type(selector: string, value: string) {
    const input = el.querySelector<HTMLInputElement>(selector)!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  afterEach(() => http.verify());

  it('lists schools and hides the add button from non-admins', async () => {
    await setup('user');
    expect(el.textContent).toContain('Braeburn Garden Estate');
    expect(button('Add school')).toBeUndefined();
    expect(el.textContent).toContain('Only administrators can add schools.');
  });

  it('validates before calling the API', async () => {
    await setup('admin');
    button('Add school').click();
    await fixture.whenStable();
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    expect(el.textContent).toContain('Enter the school name.');
    expect(el.textContent).toContain('Select at least one curriculum.');
    http.expectNone(API);
  });

  it('adds a school with a normalised code', async () => {
    await setup('admin');
    button('Add school').click();
    await fixture.whenStable();
    type('#school-name', 'Braeburn School');
    type('#school-code', 'Braeburn School');
    el.querySelector<HTMLInputElement>('input[type=checkbox]')!.click();
    el.querySelector('form')!.dispatchEvent(new Event('submit'));

    const req = http.expectOne(API);
    expect(req.request.body).toEqual({
      name: 'Braeburn School',
      code: 'braeburn-school',
      curricula: ['ib'],
    });
    req.flush({ ...req.request.body, is_active: true });
    await fixture.whenStable();

    expect(el.querySelector('form')).toBeNull();
    expect(el.textContent).toContain('Braeburn School was added.');
    expect(
      [...el.querySelectorAll('tbody tr')].map((r) => r.firstElementChild?.textContent?.trim()),
    ).toEqual(['Braeburn Garden Estate', 'Braeburn School']);
  });

  it('shows a conflict on the code field', async () => {
    await setup('admin');
    button('Add school').click();
    await fixture.whenStable();
    type('#school-name', 'Duplicate');
    type('#school-code', 'bge');
    el.querySelector<HTMLInputElement>('input[type=checkbox]')!.click();
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    http
      .expectOne(API)
      .flush({ detail: "School 'bge' already exists" }, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();

    expect(el.querySelector('[role=alert]')?.textContent).toContain("School 'bge' already exists");
    expect(el.textContent).toContain('This code is already used by another school.');
    expect(el.querySelector('#school-code')?.getAttribute('aria-invalid')).toBe('true');
  });
});
