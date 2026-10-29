import { useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import TimelinePage from './pages/TimelinePage';
import DashboardPage from './pages/DashboardPage';
import LiveViewPage from './pages/LiveViewPage';
import CamerasPage from './pages/CamerasPage';
import SettingsPage from './pages/SettingsPage';
import LogsPage from './pages/LogsPage';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';

export default function App() {
  const navigate = useNavigate();

  useEffect(() => {
    function onUnauthorized() {
      navigate('/login', { replace: true });
    }
    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized);
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/timeline" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/live" element={<LiveViewPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/logs" element={<LogsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/timeline" replace />} />
    </Routes>
  );
}