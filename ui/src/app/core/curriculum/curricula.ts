export interface Curriculum {
  /** URL segment, e.g. `/ib/<school>/overview`. */
  slug: string;
  name: string;
  /** Programmes covered, shown under the name in the dashboard sidebar. */
  programmes: string;
  /** URL of the curriculum's logo image. */
  imageUrl: string;
  description: string;
  available: boolean;
  /** Placeholder mark until official logo files are added to `public/images`. */
  mark: { text: string; class: string };
}

export const CURRICULA: readonly Curriculum[] = [
  {
    slug: 'ib',
    name: 'IB',
    imageUrl: '/images/ib.png',
    programmes: 'Diploma & Career-related',
    description: 'Diploma Programme and Career-related Programme results.',
    available: true,
    mark: {
      text: 'ib',
      class: 'bg-gradient-to-br from-sky-400 to-blue-800 font-display text-4xl lowercase',
    },
  },
  {
    slug: 'igcse',
    name: 'IGCSE',
    imageUrl: '/images/igcse.png',
    programmes: 'Cambridge IGCSE',
    description: 'Subject grades and cohort comparisons.',
    available: false,
    mark: { text: 'IGCSE', class: 'bg-orange-400 text-base tracking-wide' },
  },
  {
    slug: 'a-level',
    name: 'A-Level',
    imageUrl: '/images/a-level.webp',
    programmes: 'Cambridge A-Level',
    description: 'Subject grades and cohort comparisons.',
    available: false,
    mark: { text: 'A', class: 'bg-amber-400 font-display text-4xl' },
  },
];

export function findCurriculum(slug: string | null | undefined): Curriculum | undefined {
  return CURRICULA.find((c) => c.slug === slug);
}
