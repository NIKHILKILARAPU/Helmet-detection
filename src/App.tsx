import React, { useState } from 'react';
import { AppProvider, useApp } from './context';
import { Header } from './components/common/Header';
import { Sidebar } from './components/common/Sidebar';
import { ToastContainer } from './components/common/ToastContainer';
import { AdminDashboard } from './components/admin/AdminDashboard';
import { ReviewerQueue } from './components/reviewer/ReviewerQueue';
import { CameraOperatorView } from './components/operator/CameraOperatorView';
import { CitizenPortal } from './components/citizen/CitizenPortal';

const AppLayout: React.FC = () => {
  const { currentRole } = useApp();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const getPageTitle = () => {
    switch (currentRole) {
      case 'admin':
        return 'Enforcement Management & System Intelligence';
      case 'reviewer':
        return 'Candidate Review Desk & Draft Sanction';
      case 'operator':
        return 'Live Surveillance Camera & Capture Stream';
      case 'citizen':
        return 'Citizen Traffic Safety Portal';
      default:
        return 'TrafficGuard AI System';
    }
  };

  const getBreadcrumbs = () => {
    const roleLabels: Record<string, string> = {
      admin: 'Admin Center',
      reviewer: 'Review Officer',
      operator: 'Camera Surveillance',
      citizen: 'Citizen Portal'
    };
    return ['TrafficGuard AI', roleLabels[currentRole] || 'Workspace'];
  };

  return (
    <div className="flex h-screen bg-[#F5F7FA] overflow-hidden">
      {/* Collapsible / Responsive Sidebar */}
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main View Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header with Breadcrumbs & Role Switcher */}
        <Header
          onToggleSidebar={() => setIsMobileSidebarOpen(true)}
          pageTitle={getPageTitle()}
          breadcrumb={getBreadcrumbs()}
        />

        {/* Scrollable Page Canvas */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">
            {currentRole === 'admin' && <AdminDashboard />}
            {currentRole === 'reviewer' && <ReviewerQueue />}
            {currentRole === 'operator' && <CameraOperatorView />}
            {currentRole === 'citizen' && <CitizenPortal />}
          </div>
        </main>
      </div>

      {/* Non-intrusive Toast Container */}
      <ToastContainer />
    </div>
  );
};

export function App() {
  return (
    <AppProvider>
      <AppLayout />
    </AppProvider>
  );
}

export default App;
