import { request } from './client';

export interface LegalArticleInfo {
  id: number; law: string; book: string | null; chapter: string | null;
  article_no: string; content: string; tags: string[];
}

export const getLegalArticles = (params?: Record<string, string>) => {
  const q = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<LegalArticleInfo[]>(`/api/legal/articles${q}`);
};
export const getLegalArticle = (id: number) => request<LegalArticleInfo>(`/api/legal/articles/${id}`);
