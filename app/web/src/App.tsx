import { Outlet, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import { useToasts } from './hooks/useToast';
import Topbar from './components/Topbar';
import SideMenu from './components/SideMenu';
import PostSelector from './components/PostSelector';
import Toast from './components/Toast';

export default function App() {
  const { user, loading, needPostSelect, setNeedPostSelect } = useAuth();
  const location = useLocation();
  const toasts = useToasts();

  if (loading) return <div className="loading"><span className="spinner" />加载中...</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;

  const inWorkbench = location.pathname.startsWith('/contract/');

  return (
    <>
      <Topbar />
      {inWorkbench ? (
        <div className="workbench">
          <Outlet />
        </div>
      ) : (
        <div className="app-body">
          <SideMenu />
          <div className="content-area">
            <Outlet />
          </div>
        </div>
      )}
      {needPostSelect && (
        <PostSelector onClose={() => setNeedPostSelect(false)} />
      )}
      <Toast toasts={toasts} />
    </>
  );
}
