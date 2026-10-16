import React, { useState } from 'react';
import type { ReactNode } from 'react';
import { useApp } from '../context';
import { Header } from '../components/common/Header';
import { Sidebar } from '../components/common/Sidebar';
import { ToastContainer } from '../components/common/ToastContainer';

interface MainLayoutProps {
  children: ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const { currentRole } = useApp();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const getPageTitle = () => {
    switch (currentRole) {
      case 'admin':
        return 'Government Administration & Enforcement Controls';
      case 'reviewer':
        return 'Traffic Adjudication Officer Review Desk';
      case 'operator':
        return 'Surveillance Camera Feeds & AI Edge Monitoring';
      case 'supervisor':
        return 'Supervisory Command & Enforcement Analytics';
      default:
        return 'TrafficGuard AI — Government Enforcement System';
    }
  };

  const getBreadcrumbs = () => {
    const roleLabels: Record<string, string> = {
      admin: 'Government Admin',
      reviewer: 'Traffic Officer / Reviewer',
      operator: 'Camera Surveillance',
      supervisor: 'Supervisory Directorate'
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
            {children}
          </div>
        </main>
      </div>

      {/* Non-intrusive Toast Container */}
      <ToastContainer />
    </div>
  );
};
