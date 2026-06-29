import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useState } from 'react';

type MenuItem = { path: string; label: string; icon: string; admin?: boolean } | { sep: string };

const MENU: MenuItem[] = [
  { path: '/', label: '全部合同', icon: '📁' },
  { sep: '知识库' },
  { path: '/legal', label: '法律法规', icon: '⚖' },
  { path: '/legal?tab=rule', label: '审查规则', icon: '📐' },
  { sep: '系统管理' },
  { path: '/admin/users', label: '用户管理', icon: '👤', admin: true },
  { path: '/admin/audit', label: '审计日志', icon: '🛡', admin: true },
  { path: '/admin/config', label: '系统配置', icon: '⚙', admin: true },
];

export default function SideMenu() {
  const { user, logout, setNeedPostSelect } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [showMenu, setShowMenu] = useState(false);
  const isAdmin = user?.role === '管理员';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActive = (m: Extract<MenuItem, { path: string }>) => {
    if (m.path === '/legal?tab=rule') return location.pathname === '/legal' && location.search === '?tab=rule';
    if (m.path === '/legal') return location.pathname === '/legal' && location.search !== '?tab=rule';
    if (m.path === '/') return location.pathname === '/';
    return location.pathname.startsWith(m.path);
  };

  return (
    <nav className="sidemenu">
      {MENU.map((m, i) => {
        if ('sep' in m) {
          if (m.sep === '系统管理' && !isAdmin) return null;
          return <div key={i} className="menu-sep">{m.sep}</div>;
        }
        if (m.admin && !isAdmin) return null;
        return (
          <Link key={m.path} to={m.path} className={`menu-item${isActive(m) ? ' active' : ''}`}>
            <span className="mi-ico">{m.icon}</span><span>{m.label}</span>
          </Link>
        );
      })}
      <div className="side-user" onClick={() => setShowMenu(!showMenu)}>
        <div className="su-avatar">{user?.display_name?.[0] || 'U'}</div>
        <div className="su-info">
          <div className="su-name">{user?.display_name}</div>
          <div className="su-post">岗位：{user?.post || '-'}</div>
        </div>
        <span className="su-caret">▾</span>
        {showMenu && (
          <div className="su-menu" onClick={e => e.stopPropagation()}>
            <div className="su-mi" onClick={() => { setShowMenu(false); navigate('/my-focus'); }}>我的关注点</div>
            <div className="su-mi" onClick={() => { setShowMenu(false); setNeedPostSelect(true); }}>更换岗位</div>
            <div className="su-mi" onClick={handleLogout}>退出登录</div>
          </div>
        )}
      </div>
    </nav>
  );
}
