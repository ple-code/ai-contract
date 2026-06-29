import { request, sseStream } from './client';

export interface FindingInfo {
  id: number; clause_code: string; risk_level: string;
  finding: string; suggestion: string;
  legal_basis: { law: string; article_no?: string; article?: string; snippet?: string; point?: string }[];
  stance_note: string | null;
}
export interface ReviewDetail {
  id: number; version_id: number; stance: string; model_used: string;
  status: string; findings: FindingInfo[]; created_at: string;
}

export const startReview = (
  body: { version_id: number; stance: string },
  onEvent: (e: { event: string; data: string }) => void,
  onDone: () => void,
  onError: (e: Error) => void
) => sseStream('/api/reviews', body, onEvent, onDone, onError);

export const getReview = (id: number) => request<ReviewDetail>(`/api/reviews/${id}`);
export const getReviewByVersion = (vid: number, stance?: string) =>
  request<ReviewDetail>(`/api/reviews/by-version/${vid}${stance ? `?stance=${stance}` : ''}`);
export const updateStance = (id: number, stance: string) =>
  request<ReviewDetail>(`/api/reviews/${id}/stance`, { method: 'PUT', body: JSON.stringify({ stance }) });
