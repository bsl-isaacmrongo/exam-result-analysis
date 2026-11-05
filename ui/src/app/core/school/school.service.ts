import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { API_BASE_URL } from '../api/api-config';
import { NewSchool, School } from './school.models';

/** Active schools per curriculum, fetched from the API and kept for the app session. */
@Injectable({ providedIn: 'root' })
export class SchoolService {
  private readonly http = inject(HttpClient);
  private readonly api = `${inject(API_BASE_URL)}/api/schools`;
  private readonly loaded = signal<ReadonlyMap<string, readonly School[]>>(new Map());
  private readonly pending = new Map<string, Promise<readonly School[]>>();

  /** Schools already loaded for `curriculum`; `undefined` until first fetched. Reactive. */
  cached(curriculum: string): readonly School[] | undefined {
    return this.loaded().get(curriculum);
  }

  /** Cached list when available, unless `refresh` asks for a fresh copy. */
  forCurriculum(curriculum: string, { refresh = false } = {}): Promise<readonly School[]> {
    const known = this.loaded().get(curriculum);
    if (known && !refresh) return Promise.resolve(known);

    let request = this.pending.get(curriculum);
    if (!request) {
      request = firstValueFrom(this.http.get<School[]>(this.api, { params: { curriculum } }))
        .then((schools) => {
          this.loaded.update((map) => new Map(map).set(curriculum, schools));
          return schools;
        })
        .finally(() => this.pending.delete(curriculum));
      this.pending.set(curriculum, request);
    }
    return request;
  }

  /** Every school; inactive ones are included only for admins (the API decides). */
  listAll(): Promise<School[]> {
    return firstValueFrom(
      this.http.get<School[]>(this.api, { params: { include_inactive: true } }),
    );
  }

  async create(school: NewSchool): Promise<School> {
    const created = await firstValueFrom(this.http.post<School>(this.api, school));
    this.refreshLoaded();
    return created;
  }

  /** Re-fetch cached curricula in the background; old lists stay visible until replaced. */
  private refreshLoaded(): void {
    for (const curriculum of this.loaded().keys()) {
      this.forCurriculum(curriculum, { refresh: true }).catch(() => undefined);
    }
  }
}

export interface SchoolFormErrors {
  /** Message for the whole form. */
  message: string;
  /** Messages keyed by field name, from API validation errors. */
  fields: Partial<Record<keyof NewSchool, string>>;
}

/** Turn an API error from the schools endpoints into user-facing messages. */
export function schoolErrorMessage(error: unknown): SchoolFormErrors {
  if (!(error instanceof HttpErrorResponse)) {
    return { message: 'Something went wrong. Please try again.', fields: {} };
  }
  const detail = (error.error as { detail?: unknown } | null)?.detail;
  switch (error.status) {
    case 0:
      return { message: "Can't reach the server. Check your connection.", fields: {} };
    case 403:
      return { message: 'Only administrators can manage schools.', fields: {} };
    case 409:
      return {
        message: typeof detail === 'string' ? detail : 'That school already exists.',
        fields: { code: 'This code is already used by another school.' },
      };
    case 422: {
      const fields: SchoolFormErrors['fields'] = {};
      if (Array.isArray(detail)) {
        for (const item of detail as { loc?: unknown[]; msg?: string }[]) {
          const field = item.loc?.[1];
          if (field === 'code' || field === 'name' || field === 'curricula') {
            fields[field] ??= (item.msg ?? 'Invalid value').replace(/^Value error, /, '');
          }
        }
      }
      return { message: 'Please fix the highlighted fields.', fields };
    }
    default:
      return { message: 'The school could not be saved. Please try again.', fields: {} };
  }
}
