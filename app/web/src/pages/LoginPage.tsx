import { useState, type FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import PasswordInput from '../components/PasswordInput';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">明　衡</div>
        <div className="login-sub">合同审核 AI · 初审工作台</div>
        <div className="field">
          <label>账号</label>
          <input value={username} onChange={e => setUsername(e.target.value)} placeholder="请输入账号" autoFocus />
        </div>
        <div className="field">
          <label>密码</label>
          <PasswordInput value={password} onChange={e => setPassword(e.target.value)} placeholder="请输入密码" />
        </div>
        {error && <div className="login-error">{error}</div>}
        <button className="login-btn" type="submit" disabled={loading || !username || !password}>
          {loading ? '登录中...' : '登 录'}
        </button>
        <div className="login-hint">账号由管理员统一开通 · 首次登录需选择岗位</div>
      </form>
    </div>
  );
}
