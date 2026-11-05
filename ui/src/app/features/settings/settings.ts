import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';

import { AuthService } from '../../core/auth/auth.service';
import { CURRICULA, findCurriculum } from '../../core/curriculum/curricula';
import { ALL_SCHOOLS, School, SCHOOL_CODE_PATTERN } from '../../core/school/school.models';
import { SchoolService, schoolErrorMessage } from '../../core/school/school.service';
import { Icon } from '../../shared/ui/icon';

function schoolCodeValidator(control: AbstractControl<string>): ValidationErrors | null {
  const code = control.value.trim().toLowerCase();
  if (!code) return null;
  if (code === ALL_SCHOOLS) return { reserved: true };
  return SCHOOL_CODE_PATTERN.test(code) ? null : { pattern: true };
}

function atLeastOne(control: AbstractControl<Record<string, boolean>>): ValidationErrors | null {
  return Object.values(control.value).some(Boolean) ? null : { required: true };
}

/** App settings. Schools: everyone can view; admins can add. */
@Component({
  selector: 'app-settings',
  imports: [ReactiveFormsModule, Icon],
  templateUrl: './settings.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Settings {
  private readonly auth = inject(AuthService);
  private readonly schoolService = inject(SchoolService);
  private readonly injector = inject(Injector);
  private readonly nameInput = viewChild<ElementRef<HTMLInputElement>>('nameInput');

  protected readonly curricula = CURRICULA;
  protected readonly isAdmin = computed(() => this.auth.user()?.role === 'admin');

  protected readonly schools = signal<School[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal(false);

  protected readonly formOpen = signal(false);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly serverErrors = signal<Partial<Record<'code' | 'name' | 'curricula', string>>>(
    {},
  );
  /** Name of the school just added, for the confirmation banner. */
  protected readonly added = signal<string | null>(null);

  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly form = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(255)]],
    code: ['', [Validators.required, schoolCodeValidator]],
    curricula: this.fb.group(
      Object.fromEntries(CURRICULA.map((c) => [c.slug, false])) as Record<string, boolean>,
      { validators: atLeastOne },
    ),
  });

  constructor() {
    void this.load();
  }

  protected curriculumName(slug: string): string {
    return findCurriculum(slug)?.name ?? slug;
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.loadError.set(false);
    try {
      this.schools.set(await this.schoolService.listAll());
    } catch {
      this.loadError.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  protected openForm(): void {
    this.formOpen.set(true);
    this.added.set(null);
    afterNextRender(() => this.nameInput()?.nativeElement.focus(), { injector: this.injector });
  }

  protected cancel(): void {
    this.formOpen.set(false);
    this.resetForm();
  }

  /** Lowercase the code as the user types; the API stores it lowercased anyway. */
  protected normaliseCode(): void {
    const control = this.form.controls.code;
    const value = control.value.toLowerCase().replace(/\s+/g, '-');
    if (value !== control.value) control.setValue(value);
    this.clearServerError('code');
  }

  protected clearServerError(field: 'code' | 'name' | 'curricula'): void {
    if (this.serverErrors()[field]) {
      this.serverErrors.update(({ [field]: _, ...rest }) => rest);
    }
  }

  protected showError(field: 'code' | 'name' | 'curricula'): boolean {
    const control = this.form.controls[field];
    return (control.invalid && control.touched) || !!this.serverErrors()[field];
  }

  protected async submit(): Promise<void> {
    if (this.saving()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { name, code, curricula } = this.form.getRawValue();
    this.saving.set(true);
    this.formError.set(null);
    this.serverErrors.set({});
    try {
      const school = await this.schoolService.create({
        name: name.trim(),
        code: code.trim().toLowerCase(),
        curricula: CURRICULA.map((c) => c.slug).filter((slug) => curricula[slug]),
      });
      this.schools.update((list) => [...list, school].sort((a, b) => a.name.localeCompare(b.name)));
      this.added.set(school.name);
      this.formOpen.set(false);
      this.resetForm();
    } catch (error) {
      const { message, fields } = schoolErrorMessage(error);
      this.formError.set(message);
      this.serverErrors.set(fields);
    } finally {
      this.saving.set(false);
    }
  }

  private resetForm(): void {
    this.form.reset();
    this.formError.set(null);
    this.serverErrors.set({});
  }
}
