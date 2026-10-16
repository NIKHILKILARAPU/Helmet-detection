import React, { useState } from 'react';
import { 
  Bell, 
  Menu, 
  Sparkles, 
  Check, 
  Laptop, 
  Users, 
  Camera, 
  FileCheck,
  ChevronDown
} from 'lucide-react';
import { useApp } from '../../context';
import type { UserRole } from '../../types';

interface HeaderProps {
  onToggleSidebar: () => void;
  pageTitle: string;
  breadcrumb?: string[];
}

export const Header: React.FC<HeaderProps> = ({ 
  onToggleSidebar, 
  pageTitle, 
  breadcrumb = ['TrafficGuard AI'] 
}) => {
  const { 
    currentRole, 
    setCurrentRole, 
    currentUser, 
    systemHealth,
    addToast
  } = useApp();

  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  const rolesList: { id: UserRole; label: string; icon: React.ReactNode; desc: string }[] = [
    {
      id: 'admin',
      label: 'Admin Dashboard',
      icon: <Users className="w-4 h-4 text-indigo-600" />,
      desc: 'Enforcement metrics, trends, person directory, system health'
    },
    {
      id: 'reviewer',
      label: 'Reviewer / Management',
      icon: <FileCheck className="w-4 h-4 text-blue-600" />,
      desc: 'Review candidate queue, inspect bounding boxes, approve draft'
    },
    {
      id: 'operator',
      label: 'Camera Operator',
      icon: <Camera className="w-4 h-4 text-emerald-600" />,
      desc: 'Webcam feed, live snapshots, AI demo pipeline test'
    },
    {
      id: 'citizen',
      label: 'Registered-Person Portal',
      icon: <Laptop className="w-4 h-4 text-amber-600" />,
      desc: 'Plain language view, linked vehicles, dispute submission'
    }
  ];

  const handleSelectRole = (role: UserRole) => {
    setCurrentRole(role);
    setShowRoleMenu(false);
    addToast({
      type: 'info',
      title: 'Demo Role Switched',
      message: `Previewing interface as ${rolesList.find(r => r.id === role)?.label}`
    });
  };

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200">
      {/* Demo Warning Banner */}
      <div className="bg-[#17324D] text-slate-100 px-4 py-1.5 text-xs flex flex-wrap items-center justify-between border-b border-slate-700">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 font-semibold text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded text-[11px] border border-amber-800">
            <Sparkles className="w-3 h-3 text-amber-400" />
            DEVELOPMENT DEMO MODE
          </span>
          <span className="text-slate-300 hidden sm:inline">
            FastAPI/MongoDB integration ready • Frontend role switcher active
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className={`w-2 h-2 rounded-full ${systemHealth.isBackendConnected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            <span className="text-slate-300">
              {systemHealth.isBackendConnected ? 'FastAPI Connected' : 'Demo State (In-Memory)'}
            </span>
          </div>

          {/* Quick Demo Switcher Button in Header Bar */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowRoleMenu(!showRoleMenu)}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs transition-colors"
            >
              <span>Role: <strong className="capitalize">{currentRole}</strong></span>
              <ChevronDown className="w-3 h-3" />
            </button>

            {/* Dropdown Menu */}
            {showRoleMenu && (
              <div className="absolute right-0 mt-2 w-80 rounded-xl bg-white text-slate-900 shadow-xl border border-slate-200 p-2 z-50">
                <div className="p-2 border-b border-slate-100">
                  <div className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Role Preview Switcher
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    For reviewer and testing only. Production uses JWT/OAuth2.
                  </p>
                </div>
                <div className="py-1">
                  {rolesList.map(r => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => handleSelectRole(r.id)}
                      className={`w-full text-left p-2.5 rounded-lg text-xs flex items-start gap-2.5 transition-colors ${
                        currentRole === r.id ? 'bg-blue-50 text-blue-900 font-semibold' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div className="mt-0.5">{r.icon}</div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span>{r.label}</span>
                          {currentRole === r.id && <Check className="w-4 h-4 text-blue-600" />}
                        </div>
                        <div className="text-[11px] text-slate-500 font-normal mt-0.5">{r.desc}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main App Navigation Bar */}
      <div className="px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        {/* Left: Mobile Toggle & Page Title & Breadcrumbs */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
            aria-label="Open sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              {breadcrumb.map((b, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span>/</span>}
                  <span className={i === breadcrumb.length - 1 ? 'text-slate-600 font-medium' : ''}>
                    {b}
                  </span>
                </React.Fragment>
              ))}
            </div>
            <h1 className="text-lg font-bold text-[#17324D] tracking-tight mt-0.5">
              {pageTitle}
            </h1>
          </div>
        </div>

        {/* Right: Notifications & Current User Info */}
        <div className="flex items-center gap-3">
          {/* Notifications Button */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowNotifications(!showNotifications)}
              className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 relative transition-colors"
              aria-label="View notifications"
            >
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-500"></span>
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-72 rounded-xl bg-white shadow-xl border border-slate-200 p-3 z-50">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <span className="text-xs font-bold text-slate-800">System Notifications</span>
                  <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">Demo</span>
                </div>
                <div className="py-2 space-y-2 text-xs">
                  <div className="p-2 rounded-lg bg-amber-50 border border-amber-100 text-amber-900">
                    <span className="font-semibold block text-[11px]">Pending Review Queue</span>
                    <span className="text-[11px] text-amber-800">14 candidate frames waiting for human verification.</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 text-slate-700">
                    <span className="font-semibold block text-[11px]">Camera CAM-04 Live</span>
                    <span className="text-[11px] text-slate-600">Koramangala 80ft Road stream active at 30 FPS.</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="h-6 w-px bg-slate-200" />

          {/* User Profile Summary */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-[#17324D] text-white flex items-center justify-center text-xs font-bold shadow-xs">
              {currentUser.name.charAt(0)}
            </div>
            <div className="hidden sm:block text-left">
              <div className="text-xs font-bold text-slate-800 leading-tight">
                {currentUser.name}
              </div>
              <div className="text-[11px] text-slate-500 leading-tight capitalize">
                {currentRole} • {currentUser.department.split(' ')[0]}
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
