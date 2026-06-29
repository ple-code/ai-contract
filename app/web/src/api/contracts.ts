import { request, upload } from './client';

export interface ContractBrief {
  id: number; name: string; no: string; type_code: string; type_name: string;
  uploader_name: string; current_version_no: number; current_version_id: number;
  has_baseline: boolean; status: string;
  created_at: string; updated_at: string;
}
export interface ContractListRes { items: ContractBrief[]; total: number }
export interface ContractTypeInfo { code: string; name: string; supported: boolean }
export interface ContractOption { id: number; name: string; no: string; current_version_no: number | null }
export interface ClauseInfo {
  id: number; code: string; title: string; text: string; level: number;
  type_tags: string[]; locator: Record<string, unknown>;
}
export interface ContractDetail {
  id: number; name: string; no: string; type_code: string; type_name: string;
  uploader_name: string; current_version_id: number; current_version_no: number;
  status: string; baseline_kind: string | null; baseline_label: string | null;
  clauses: ClauseInfo[]; created_at: string;
}
export interface ChangeLogInfo {
  id: number; version_no: number; event_type: string; clause_code: string | null;
  detail: string | null; actor_user_id: number | null; actor_post: string | null; created_at: string;
}

export interface FieldChange {
  field: string; from_value: string; to_value: string; change_type: string;
}

export interface UploadResult {
  ok: boolean; contract_id: number; version_id: number;
  type_detected: string; confidence: number; clause_count: number;
  error?: string; message?: string;
  // 重复合同识别命中时返回：method 区分「编号撞号」与「AI 相似度」
  method?: 'contract_no' | 'ai_similarity';
  match?: { id: number; name: string; no: string | null; current_version_no: number | null };
  parsed_contract_no?: string;
}

export const getContracts = (params?: Record<string, string>) => {
  const q = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<ContractListRes>(`/api/contracts${q}`);
};
export const getContractTypes = () => request<ContractTypeInfo[]>('/api/contract-types');
export const getContractOptions = () => request<ContractOption[]>('/api/contracts/options');
export const uploadContract = (form: FormData) => upload<UploadResult>('/api/contracts', form);
export const getContract = (id: number) => request<ContractDetail>(`/api/contracts/${id}`);
export const compareContract = (id: number, body: { baseline_version_id?: number }) =>
  request<unknown>(`/api/contracts/${id}/compare`, { method: 'POST', body: JSON.stringify(body) });
export const getChangeLogs = (id: number) => request<ChangeLogInfo[]>(`/api/contracts/${id}/change-logs`);
// 下载指定版本的原始上传源文件（变更记录每个版本后挂下载按钮）
export const downloadVersionSource = (contractId: number, versionNo: number) =>
  `/api/contracts/${contractId}/versions/${versionNo}/download-source`;
export const getFieldSummary = (id: number) => request<FieldChange[]>(`/api/contracts/${id}/field-summary`);
export const getAiStatus = () => request<{ ready: boolean; message?: string }>('/api/ai-status');
export const getPostFocus = () => request<{ post_focus: Record<string, string[]> }>('/api/post-focus');
export const getPersonalFocus = () => request<{ personal_focus: string[] }>('/api/me/personal-focus');
export const updatePersonalFocus = (personal_focus: string[]) =>
  request<{ ok: boolean }>('/api/me/personal-focus', { method: 'PUT', body: JSON.stringify({ personal_focus }) });
