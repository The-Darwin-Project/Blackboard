// ui/src/utils/eventFormat.ts

import type { SubjectType } from '../api/types';

export function extractReasonDisplay(reason: string): string {
  if (!reason.startsWith('---')) return reason;
  const match = reason.match(/plan:\s*"?([^"\n]+)"?/);
  return match?.[1]?.trim() || reason.replace(/---[\s\S]*?---/, '').trim() || reason;
}

export function resolveSubjectType(subjectType?: SubjectType, service?: string): SubjectType | undefined {
  if (subjectType && subjectType !== 'service') return subjectType;
  if (service && service.includes('@kargo-')) return 'kargo_stage';
  return subjectType;
}
