import { request } from './client';

export interface LoginReq { username: string; password: string }
export interface LoginRes { token: string; user: UserInfo }
export interface UserInfo { id: number; username: string; display_name: string; post: string; role: string }
export interface PrefInfo { default_post: string | null; remember_post: boolean }
export interface MeResponse { user: UserInfo; pref: PrefInfo }

export const login = (data: LoginReq) => request<LoginRes>('/api/auth/login', { method: 'POST', body: JSON.stringify(data) });
export const logout = () => request<void>('/api/auth/logout', { method: 'POST' });
export const getMe = () => request<MeResponse>('/api/me');
export const updatePref = (data: Partial<PrefInfo>) => request<PrefInfo>('/api/me/pref', { method: 'PUT', body: JSON.stringify(data) });
