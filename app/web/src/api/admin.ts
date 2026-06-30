import { request } from './client';

export interface ModelConfigInfo {
  gateway_base_url: string; default_model: string; sensitive_model: string; has_token: boolean;
  post_focus: Record<string, string[]> | null;
}
export interface UserBrief {
  id: number; username: string; display_name: string; post: string; role: string; enabled: boolean; created_at: string;
}
export interface AuditLogInfo {
  id: number; user_id: number | null; username: string | null; user_post: string | null;
  action: string; target_type: string | null; target_id: string | null; target_label: string | null;
  ip: string | null; detail: Record<string, unknown> | null; created_at: string;
}
export interface AuditListRes { items: AuditLogInfo[]; total: number }

export const getModelConfig = () => request<ModelConfigInfo>('/api/admin/model-config');
export const updateModelConfig = (data: Record<string, unknown>) =>
  request<ModelConfigInfo>('/api/admin/model-config', { method: 'PUT', body: JSON.stringify(data) });
export const testModelConfig = (data?: Record<string, string>) =>
  request<{ ok: boolean; message?: string; error?: string; response?: string }>(
    '/api/admin/model-config/test',
    { method: 'POST', body: JSON.stringify(data || {}) },
  );

export const getUsers = () => request<UserBrief[]>('/api/admin/users');
export const createUser = (data: Record<string, string>) =>
  request<UserBrief>('/api/admin/users', { method: 'POST', body: JSON.stringify(data) });
export const updateUser = (id: number, data: Record<string, unknown>) =>
  request<UserBrief>(`/api/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });

export const getAuditLogs = (params?: Record<string, string>) => {
  const q = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<AuditListRes>(`/api/admin/audit-logs${q}`);
};
