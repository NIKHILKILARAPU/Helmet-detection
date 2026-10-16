import React from 'react';
import { 
  LayoutDashboard, 
  ShieldCheck, 
  Camera, 
  Users, 
  FileText, 
  Activity, 
  UserCheck, 
  ChevronLeft, 
  ChevronRight, 
  Car, 
  HelpCircle,
  FileCheck2,
  X
} from 'lucide-react';
import { useApp } from '../../context';
import type { UserRole } from '../../types';

interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile
}) => {
  const { currentRole, setCurrentRole, activeNavTab, setActiveNavTab } = useApp();

  const getNavLinks = () => {
    switch (currentRole) {
      case 'admin':
        return [
          { id: 'overview', label: 'Enforcement Overview', icon: <LayoutDashboard className="w-4 h-4" /> },
          { id: 'violations', label: 'Recent Violations', icon: <FileText className="w-4 h-4" /> },
          { id: 'persons', label: 'Registered Persons', icon: <Users className="w-4 h-4" /> },
          { id: 'users', label: 'User & Role Access', icon: <UserCheck className="w-4 h-4" /> },
          { id: 'health', label: 'System Health & AI', icon: <Activity className="w-4 h-4" /> }
        ];
      case 'reviewer':
        return [
          { id: 'queue', label: 'Review Candidate Queue', icon: <FileCheck2 className="w-4 h-4" /> },
          { id: 'audit-log', label: 'Reviewer Audit Log', icon: <FileText className="w-4 h-4" /> }
        ];
      case 'operator':
        return [
          { id: 'camera-feed', label: 'Live Camera & Capture', icon: <Camera className="w-4 h-4" /> },
          { id: 'recent-captures', label: 'Recent Camera Scans', icon: <FileText className="w-4 h-4" /> }
        ];
      case 'citizen':
        return [
          { id: 'my-portal', label: 'My Profile & Status', icon: <UserCheck className="w-4 h-4" /> },
          { id: 'my-vehicles', label: 'Linked Vehicles', icon: <Car className="w-4 h-4" /> },
          { id: 'my-cases', label: 'Traffic Observations', icon: <FileText className="w-4 h-4" /> },
          { id: 'help-support', label: 'Help & Dispute Support', icon: <HelpCircle className="w-4 h-4" /> }
        ];
      default:
        return [];
    }
  };

  const navLinks = getNavLinks();

  const roleColors: Record<UserRole, { badge: string; text: string }> = {
    admin: { badge: 'bg-indigo-100 text-indigo-800', text: 'Admin Enforcement' },
    reviewer: { badge: 'bg-blue-100 text-blue-800', text: 'Review Officer' },
    operator: { badge: 'bg-emerald-100 text-emerald-800', text: 'Camera Operator' },
    citizen: { badge: 'bg-amber-100 text-amber-800', text: 'Registered Citizen' }
  };

  const content = (
    <div className="flex flex-col h-full bg-[#17324D] text-slate-200 select-none">
      {/* Brand Logo & Title */}
      <div className="p-4 border-b border-slate-700/80 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          {(!isCollapsed || isMobileOpen) && (
            <div className="min-w-0">
              <div className="text-sm font-bold text-white tracking-wide truncate">
                TrafficGuard AI
              </div>
              <div className="text-[10px] text-slate-300 font-medium">
                Helmet &amp; E-Challan System
              </div>
            </div>
          )}
        </div>

        {/* Mobile Close Button */}
        {isMobileOpen && (
          <button 
            type="button" 
            onClick={onCloseMobile}
            className="p-1 rounded-md text-slate-300 hover:text-white lg:hidden"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Role Pill */}
      {(!isCollapsed || isMobileOpen) && (
        <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-700/50">
          <div className="text-[10px] uppercase font-semibold text-slate-400 mb-1">
            Active Role Workspace
          </div>
          <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${roleColors[currentRole].badge}`}>
            {roleColors[currentRole].text}
          </span>
        </div>
      )}

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {navLinks.map(link => {
          const isActive = activeNavTab === link.id;
          return (
            <button
              key={link.id}
              type="button"
              onClick={() => {
                setActiveNavTab(link.id);
                if (isMobileOpen) onCloseMobile();
              }}
              title={isCollapsed && !isMobileOpen ? link.label : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                isActive 
                  ? 'bg-blue-600 text-white font-semibold shadow-xs' 
                  : 'text-slate-300 hover:bg-slate-800/70 hover:text-white'
              } ${isCollapsed && !isMobileOpen ? 'justify-center' : ''}`}
            >
              <span className="shrink-0">{link.icon}</span>
              {(!isCollapsed || isMobileOpen) && (
                <span className="truncate">{link.label}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Demo Switcher Quick Bar at Bottom */}
      {(!isCollapsed || isMobileOpen) ? (
        <div className="p-3 border-t border-slate-700/80 bg-slate-900/50">
          <div className="text-[11px] font-semibold text-slate-400 mb-2">
            Switch Demo Role:
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {(['admin', 'reviewer', 'operator', 'citizen'] as UserRole[]).map(role => (
              <button
                key={role}
                type="button"
                onClick={() => {
                  setCurrentRole(role);
                  if (isMobileOpen) onCloseMobile();
                }}
                className={`text-[11px] py-1.5 px-2 rounded font-medium capitalize text-center transition-colors ${
                  currentRole === role 
                    ? 'bg-blue-600 text-white font-bold' 
                    : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {role}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {/* Desktop Collapse Toggle Button */}
      <div className="hidden lg:block p-3 border-t border-slate-700/80">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-xs"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          {!isCollapsed && <span className="ml-2 font-medium">Collapse Menu</span>}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside 
        className={`hidden lg:block shrink-0 transition-all duration-200 border-r border-slate-800 ${
          isCollapsed ? 'w-20' : 'w-64'
        }`}
      >
        {content}
      </aside>

      {/* Mobile Drawer Overlay */}
      {isMobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div 
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs" 
            onClick={onCloseMobile} 
          />
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl">
            {content}
          </div>
        </div>
      )}
    </>
  );
};
