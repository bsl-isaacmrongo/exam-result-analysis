import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { ALL_SCHOOLS } from '../../core/school/school.models';
import {
  ExamSeries,
  IMPORT_KINDS,
  ImportKind,
  ResultImport,
  sessionLabel,
  sessionParam,
} from '../../core/results/results.models';
import { ImportError, ResultsService, importErrorMessage } from '../../core/results/results.service';
import { Icon } from '../../shared/ui/icon';

interface SessionGroup {
  key: string;
  label: string;
  year: number;
  session: ExamSeries;
  imports: Partial<Record<ImportKind, ResultImport>>;
}

/** Upload CEM baseline and IB results workbooks (admins) and review import history. */
@Component({
  selector: 'app-imports',
  imports: [DatePipe, RouterLink, Icon],
  templateUrl: './imports.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Imports {
  private readonly auth = inject(AuthService);
  private readonly results = inject(ResultsService);
  private readonly fileInput = viewChild<ElementRef<HTMLInputElement>>('fileInput');

  protected readonly kinds = Object.entries(IMPORT_KINDS).map(([key, value]) => ({
    key: key as ImportKind,
    ...value,
  }));
  protected readonly kindTitle = (kind: ImportKind) => IMPORT_KINDS[kind].title;
  protected readonly sessionParam = sessionParam;

  protected readonly school = toSignal(
    inject(ActivatedRoute).paramMap.pipe(map((p) => p.get('school') ?? '')),
    { initialValue: '' },
  );
  protected readonly allSchools = computed(() => this.school() === ALL_SCHOOLS);
  protected readonly isAdmin = computed(() => this.auth.user()?.role === 'admin');
  protected readonly canImport = computed(() => this.isAdmin() && !this.allSchools());

  protected readonly imports = signal<ResultImport[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal(false);

  // Form
  protected readonly kind = signal<ImportKind>('ib_results');
  protected readonly year = signal(new Date().getFullYear());
  protected readonly series = signal<ExamSeries>(new Date().getMonth() >= 9 ? 'nov' : 'may');
  protected readonly file = signal<File | null>(null);
  protected readonly dragging = signal(false);
  protected readonly uploading = signal(false);
  protected readonly uploadError = signal<ImportError | null>(null);
  protected readonly uploaded = signal<ResultImport | null>(null);
  protected readonly confirmingDelete = signal<number | null>(null);
  protected readonly deleting = signal<number | null>(null);

  protected readonly years = computed(() => {
    const now = new Date().getFullYear();
    return Array.from({ length: 8 }, (_, i) => now + 1 - i);
  });

  /** Imports grouped by exam session, newest first, with what's missing. */
  protected readonly sessions = computed<SessionGroup[]>(() => {
    const groups = new Map<string, SessionGroup>();
    for (const item of this.imports()) {
      const key = `${item.school}-${item.year}-${item.session}`;
      let group = groups.get(key);
      if (!group) {
        const label = sessionLabel(item);
        group = {
          key,
          label: this.allSchools() ? `${label} · ${item.school.toUpperCase()}` : label,
          year: item.year,
          session: item.session,
          imports: {},
        };
        groups.set(key, group);
      }
      group.imports[item.kind] = item;
    }
    return [...groups.values()];
  });

  /** Existing import that this upload would replace. */
  protected readonly replaces = computed(() =>
    this.imports().find(
      (i) =>
        i.school === this.school() &&
        i.kind === this.kind() &&
        i.year === this.year() &&
        i.session === this.series(),
    ),
  );

  constructor() {
    effect(() => {
      const school = this.school();
      if (school) untracked(() => void this.load());
    });
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.loadError.set(false);
    try {
      this.imports.set(await this.results.listImports(this.school()));
    } catch {
      this.loadError.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  protected chooseFile(file: File | null | undefined): void {
    this.file.set(file ?? null);
    this.uploadError.set(null);
    this.uploaded.set(null);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    this.chooseFile(event.dataTransfer?.files.item(0));
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  protected setYear(value: string): void {
    const year = Number(value);
    if (Number.isInteger(year)) this.year.set(year);
  }

  protected async submit(): Promise<void> {
    const file = this.file();
    if (!file || this.uploading()) {
      if (!file) this.uploadError.set({ message: 'Choose an Excel file to import.', errors: [] });
      return;
    }
    this.uploading.set(true);
    this.uploadError.set(null);
    this.uploaded.set(null);
    try {
      const created = await this.results.upload({
        school: this.school(),
        kind: this.kind(),
        year: this.year(),
        session: this.series(),
        file,
      });
      this.uploaded.set(created);
      this.file.set(null);
      const input = this.fileInput()?.nativeElement;
      if (input) input.value = '';
      this.imports.update((list) => [created, ...list.filter((i) => !this.sameSlot(i, created))]);
    } catch (error) {
      this.uploadError.set(importErrorMessage(error));
    } finally {
      this.uploading.set(false);
    }
  }

  protected async remove(item: ResultImport): Promise<void> {
    if (this.confirmingDelete() !== item.id) {
      this.confirmingDelete.set(item.id);
      return;
    }
    this.deleting.set(item.id);
    try {
      await this.results.remove(item.id);
      this.imports.update((list) => list.filter((i) => i.id !== item.id));
      if (this.uploaded()?.id === item.id) this.uploaded.set(null);
    } catch (error) {
      this.uploadError.set(importErrorMessage(error));
    } finally {
      this.deleting.set(null);
      this.confirmingDelete.set(null);
    }
  }

  protected counts(item: ResultImport): string {
    const s = item.summary;
    if (item.kind === 'cem') return `${s.students ?? 0} students · ${s.predictions ?? 0} predictions`;
    return `${s.dp_candidates ?? 0} DP · ${s.cp_candidates ?? 0} CP · ${s.subject_results ?? 0} grades`;
  }

  protected fileSize(file: File): string {
    return file.size < 1024 * 1024
      ? `${Math.max(1, Math.round(file.size / 1024))} KB`
      : `${(file.size / 1024 / 1024).toFixed(1)} MB`;
  }

  private sameSlot(a: ResultImport, b: ResultImport): boolean {
    return a.school === b.school && a.kind === b.kind && a.year === b.year && a.session === b.session;
  }
}
