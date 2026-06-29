import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { getMe, login as apiLogin, logout as apiLogout, updatePref, type UserInfo, type PrefInfo } from '../api/auth';

interface AuthState {
  user: UserInfo | null;
  pref: PrefInfo | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setPost: (post: string, remember: boolean) => Promise<void>;
  needPostSelect: boolean;
  setNeedPostSelect: (v: boolean) => void;
  refresh: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [pref, setPref] = useState<PrefInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [needPostSelect, setNeedPostSelect] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me.user);
      setPref(me.pref);
      if (!me.user.post) setNeedPostSelect(true);
    } catch {
      setUser(null);
      setPref(null);
    }
  }, []);

  useEffect(() => { refresh().finally(() => setLoading(false)); }, [refresh]);

  const login = async (username: string, password: string) => {
    const res = await apiLogin({ username, password });
    setUser(res.user);
    if (!res.user.post) setNeedPostSelect(true);
    await refresh();
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
    setPref(null);
  };

  const setPost = async (post: string, remember: boolean) => {
    await updatePref({ default_post: post, remember_post: remember });
    await refresh();
    setNeedPostSelect(false);
  };

  return (
    <AuthCtx.Provider value={{ user, pref, loading, login, logout, setPost, needPostSelect, setNeedPostSelect, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
