import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useState } from 'react';

const POSTS = [
  { key: '法务', label: '法务', desc: '合同审核责任人\n风险条款 / 关键信息' },
  { key: '销售', label: '销售', desc: '提交合同\n交货 / 标的 / 价格' },
  { key: '商务', label: '商务', desc: '对接客户\n商务信息 / 条款回填' },
  { key: '财务', label: '财务', desc: '资金把关\n付款 / 结算 / 违约金' },
];

export default function PostSelector({ onClose }: { onClose?: () => void }) {
  const { user, setPost } = useAuth();
  const [sel, setSel] = useState(user?.post || '');
  const [remember, setRemember] = useState(false);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const confirm = async () => {
    if (!sel) return;
    setSaving(true);
    try {
      await setPost(sel, remember);
      if (onClose) onClose();
      if (location.pathname === '/login') navigate('/');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-mask">
      <div className="modal">
        <h3>请选择你的岗位</h3>
        <p className="lead">系统会按你的岗位，进入合同后自动定位到你关注的条款段落，不必逐页翻看整篇。</p>
        <div className="role-grid">
          {POSTS.map(p => (
            <div key={p.key} className={`role-card${sel === p.key ? ' sel' : ''}`} onClick={() => setSel(p.key)}>
              <div className="rname">{p.label}</div>
              <div className="rdesc">{p.desc.split('\n').map((line, i) => <div key={i}>{line}</div>)}</div>
            </div>
          ))}
        </div>
        <div className="modal-foot">
          <label className="remember">
            <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />
            记住，下次不再选择
          </label>
          <button className="confirm-btn" disabled={!sel || saving} onClick={confirm}>
            {saving ? '设置中...' : '进入系统'}
          </button>
        </div>
      </div>
    </div>
  );
}
