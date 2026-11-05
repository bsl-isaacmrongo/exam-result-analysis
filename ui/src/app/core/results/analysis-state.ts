import { computed, effect, inject, signal, untracked } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';

import {
  AnalysisResponse,
  ExamSession,
  Pathway,
  parseSessionParam,
  sessionParam,
} from './results.models';
import { ResultsService } from './results.service';

const PATHWAYS: readonly Pathway[] = ['combined', 'dp', 'cp'];

/**
 * Analysis for the current `:school`, kept in step with the `session` and
 * `pathway` query params. Call from a component's injection context.
 */
export function injectAnalysis() {
  const route = inject(ActivatedRoute);
  const router = inject(Router);
  const results = inject(ResultsService);

  const params = toSignal(route.paramMap, { initialValue: route.snapshot.paramMap });
  const query = toSignal(route.queryParamMap, { initialValue: route.snapshot.queryParamMap });

  const school = computed(() => params().get('school') ?? '');
  const requestedSession = computed(() => parseSessionParam(query().get('session')));
  const pathway = computed<Pathway>(() => {
    const value = query().get('pathway') as Pathway | null;
    return value && PATHWAYS.includes(value) ? value : 'combined';
  });

  const response = signal<AnalysisResponse | null>(null);
  const loading = signal(true);
  const error = signal(false);
  let latest = 0;

  async function load(code: string, session: ExamSession | null): Promise<void> {
    const request = ++latest;
    loading.set(true);
    error.set(false);
    try {
      const result = await results.analysis(code, session);
      if (request === latest) response.set(result);
    } catch {
      if (request === latest) error.set(true);
    } finally {
      if (request === latest) loading.set(false);
    }
  }

  effect(() => {
    const code = school();
    const session = requestedSession();
    untracked(() => void load(code, session));
  });

  function setQuery(queryParams: Record<string, string | null>): void {
    void router.navigate([], { relativeTo: route, queryParams, queryParamsHandling: 'merge' });
  }

  return {
    school,
    pathway,
    response: response.asReadonly(),
    analysis: computed(() => response()?.analysis ?? null),
    session: computed(() => response()?.session ?? null),
    sessions: computed(() => response()?.sessions ?? []),
    loading: loading.asReadonly(),
    error: error.asReadonly(),
    reload: () => load(school(), requestedSession()),
    setSession: (session: ExamSession) => setQuery({ session: sessionParam(session) }),
    setPathway: (value: Pathway) => setQuery({ pathway: value === 'combined' ? null : value }),
  };
}
