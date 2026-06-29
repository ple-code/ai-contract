import { request } from './client';

export interface ClauseReviewStateInfo {
  clause_code: string; decision: string | null; note: string | null;
  applied: boolean; applied_text_snapshot: string | null;
}
export interface VersionReviewState {
  version_id: number; states: ClauseReviewStateInfo[];
}

export const getReviewState = (vid: number) => request<VersionReviewState>(`/api/versions/${vid}/review-state`);
export const setDecision = (vid: number, code: string, decision: string | null) =>
  request<void>(`/api/versions/${vid}/clauses/${encodeURIComponent(code)}/decision`, { method: 'PUT', body: JSON.stringify({ decision }) });
export const annotate = (vid: number, code: string, note: string) =>
  request<void>(`/api/versions/${vid}/clauses/${encodeURIComponent(code)}/annotate`, { method: 'PUT', body: JSON.stringify({ note }) });
export const applySuggestion = (vid: number, code: string, text: string) =>
  request<void>(`/api/versions/${vid}/clauses/${encodeURIComponent(code)}/apply`, { method: 'POST', body: JSON.stringify({ text }) });
export const revertApply = (vid: number, code: string) =>
  request<void>(`/api/versions/${vid}/clauses/${encodeURIComponent(code)}/revert-apply`, { method: 'POST' });
export const getPreview = (vid: number) => request<unknown>(`/api/versions/${vid}/preview`);
export const completeReview = (vid: number) =>
  request<void>(`/api/versions/${vid}/complete-review`, { method: 'POST' });
