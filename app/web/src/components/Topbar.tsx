import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Topbar() {
  const { user, setNeedPostSelect } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const inWorkbench = location.pathname.startsWith('/contract/');
  const inUpload = location.pathname === '/upload';

  return (
    <header className="topbar">
      <div className="topbar-left">
        {(inWorkbench || inUpload) && (
          <button className="nav-back" onClick={() => navigate('/')}>← 全部合同</button>
        )}
        <div className="brand" onClick={() => navigate('/')} title="返回全部合同">
          <span className="mark">明　衡</span>
          <span className="sub">合同审阅工作台</span>
        </div>
      </div>
      <div className="topbar-right">
        <button className="post-chip" onClick={() => setNeedPostSelect(true)} title="点击更换岗位">
          岗位：{user?.post || '未选择'}
        </button>
      </div>
    </header>
  );
}
