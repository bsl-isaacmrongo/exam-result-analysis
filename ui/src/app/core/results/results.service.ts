import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { API_BASE_URL } from '../api/api-config';
import { AnalysisResponse, ExamSession, NewImport, ResultImport } from './results.models';

/** Imports of CEM baseline / IB results workbooks and the analysis built from them. */
@Injectable({ providedIn: 'root' })
export class ResultsService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  listImports(school: string): Promise<ResultImport[]> {
    return firstValueFrom(
      this.http.get<ResultImport[]>(`${this.base}/api/imports`, { params: { school } }),
    );
  }

  upload({ school, kind, year, session, file }: NewImport): Promise<ResultImport> {
    const body = new FormData();
    body.set('school', school);
    body.set('kind', kind);
    body.set('year', String(year));
    body.set('session', session);
    body.set('file', file, file.name);
    return firstValueFrom(this.http.post<ResultImport>(`${this.base}/api/imports`, body));
  }

  async remove(id: number): Promise<void> {
    await firstValueFrom(this.http.delete<void>(`${this.base}/api/imports/${id}`));
  }

  /** Analysis for `session`, or the latest session with results when omitted. */
  analysis(school: string, session?: ExamSession | null): Promise<AnalysisResponse> {
    let params = new HttpParams().set('school', school);
    if (session) params = params.set('year', session.year).set('session', session.session);
    return firstValueFrom(
      this.http.get<AnalysisResponse>(`${this.base}/api/analysis/ib`, { params }),
    );
  }
}

export interface ImportError {
  message: string;
  /** Row-level problems found in the workbook. */
  errors: string[];
}

/** User-facing message for a failed upload or delete. */
export function importErrorMessage(error: unknown): ImportError {
  if (!(error instanceof HttpErrorResponse)) {
    return { message: 'Something went wrong. Please try again.', errors: [] };
  }
  const detail = (error.error as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const { message, errors } = detail as { message: string; errors?: string[] };
    return { message, errors: errors ?? [] };
  }
  switch (error.status) {
    case 0:
      return { message: "Can't reach the server. Check your connection.", errors: [] };
    case 403:
      return { message: 'Only administrators can import data.', errors: [] };
    case 404:
      return { message: typeof detail === 'string' ? detail : 'Not found.', errors: [] };
    case 413:
      return { message: 'The file is too large.', errors: [] };
    case 422:
      return { message: 'Please check the form and try again.', errors: [] };
    default:
      return { message: 'The import failed. Please try again.', errors: [] };
  }
}
