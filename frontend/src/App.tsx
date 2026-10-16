import { AppProvider, useApp } from './context';
import { MainLayout } from './layouts/MainLayout';
import { AdminDashboardPage } from './pages/admin/AdminDashboardPage';
import { ReviewerQueuePage } from './pages/reviewer/ReviewerQueuePage';
import { CameraOperatorPage } from './pages/operator/CameraOperatorPage';
import { SupervisorDashboardPage } from './pages/supervisor/SupervisorDashboardPage';

const AppContent: React.FC = () => {
  const { currentRole } = useApp();

  return (
    <MainLayout>
      {currentRole === 'admin' && <AdminDashboardPage />}
      {currentRole === 'reviewer' && <ReviewerQueuePage />}
      {currentRole === 'operator' && <CameraOperatorPage />}
      {currentRole === 'supervisor' && <SupervisorDashboardPage />}
    </MainLayout>
  );
};

export function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
