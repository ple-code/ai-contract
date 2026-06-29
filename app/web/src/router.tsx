import { createBrowserRouter, Navigate } from 'react-router-dom';
import App from './App';
import LoginPage from './pages/LoginPage';
import ContractListPage from './pages/ContractListPage';
import UploadPage from './pages/UploadPage';
import WorkbenchPage from './pages/WorkbenchPage';
import SystemConfigPage from './pages/SystemConfigPage';
import UserManagePage from './pages/UserManagePage';
import AuditLogPage from './pages/AuditLogPage';
import LegalPage from './pages/LegalPage';
import MyFocusPage from './pages/MyFocusPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <ContractListPage /> },
      { path: 'upload', element: <UploadPage /> },
      { path: 'contract/:id', element: <WorkbenchPage /> },
      { path: 'admin/config', element: <SystemConfigPage /> },
      { path: 'admin/users', element: <UserManagePage /> },
      { path: 'admin/audit', element: <AuditLogPage /> },
      { path: 'legal', element: <LegalPage /> },
      { path: 'my-focus', element: <MyFocusPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
