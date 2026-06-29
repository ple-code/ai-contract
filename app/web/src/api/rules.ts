import { request } from './client';

export interface ReviewRuleInfo {
  id: number;
  name: string;
  rule_type: string;
  match_keywords: string;
  condition_desc: string;
  risk_level: string;   // high / medium / low
  suggestion: string;
}

export const getReviewRules = (params?: { level?: string; rule_type?: string; search?: string }) => {
  const q = new URLSearchParams();
  if (params?.level) q.set('level', params.level);
  if (params?.rule_type) q.set('rule_type', params.rule_type);
  if (params?.search) q.set('search', params.search);
  const qs = q.toString();
  return request<ReviewRuleInfo[]>(`/api/review-rules${qs ? `?${qs}` : ''}`);
};
