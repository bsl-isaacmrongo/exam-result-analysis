/** A school as returned by `GET /api/schools`. */
export interface School {
  /** Lowercase slug used in dashboard URLs: `/ib/<code>/overview`. */
  code: string;
  name: string;
  /** Curriculum slugs the school offers, e.g. `['ib', 'igcse']`. */
  curricula: string[];
  is_active: boolean;
}

/** Route value for the combined view across every school offering the curriculum. */
export const ALL_SCHOOLS = 'all';

/** Body for `POST /api/schools` (admin only). */
export interface NewSchool {
  code: string;
  name: string;
  curricula: string[];
}

/** Same rule as the API: 1-20 lowercase letters, digits or inner hyphens. */
export const SCHOOL_CODE_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,18}[a-z0-9])?$/;
