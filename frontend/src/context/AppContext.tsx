import React, { useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { 
  UserRole, 
  ViolationCase, 
  ToastMessage, 
  SystemHealthState, 
  RegisteredPerson, 
  UserAccount,
  CameraSourceRecord,
  OfficerActivity,
  SystemSettings,
  SystemAuditLogEntry
} from '../types';
import { 
  INITIAL_CASES, 
  INITIAL_REGISTERED_PERSONS, 
  INITIAL_USER_ACCOUNTS, 
  INITIAL_SYSTEM_HEALTH,
  INITIAL_CAMERA_SOURCES,
  INITIAL_OFFICER_ACTIVITIES,
  INITIAL_SYSTEM_SETTINGS,
  INITIAL_SYSTEM_AUDIT_LOGS
} from '../data/mockData';
import { healthService } from '../services/healthService';
import { AppContext } from './appContextDefinition';

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentRole, setCurrentRoleState] = useState<UserRole>('admin');
  const [userAccounts] = useState<UserAccount[]>(INITIAL_USER_ACCOUNTS);
  const [cases, setCases] = useState<ViolationCase[]>(INITIAL_CASES);
  const [persons, setPersons] = useState<RegisteredPerson[]>(INITIAL_REGISTERED_PERSONS);
  const [cameraSources, setCameraSources] = useState<CameraSourceRecord[]>(INITIAL_CAMERA_SOURCES);
  const [officerActivities] = useState<OfficerActivity[]>(INITIAL_OFFICER_ACTIVITIES);
  const [systemSettings, setSystemSettings] = useState<SystemSettings>(INITIAL_SYSTEM_SETTINGS);
  const [systemAuditLogs, setSystemAuditLogs] = useState<SystemAuditLogEntry[]>(INITIAL_SYSTEM_AUDIT_LOGS);
  const [selectedCase, setSelectedCase] = useState<ViolationCase | null>(null);
  const [selectedPerson, setSelectedPerson] = useState<RegisteredPerson | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealthState>(INITIAL_SYSTEM_HEALTH);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [activeNavTab, setActiveNavTab] = useState<string>('overview');

  const setCurrentRole = useCallback((role: UserRole) => {
    setCurrentRoleState(role);
    if (role === 'reviewer') {
      setActiveNavTab('queue');
    } else if (role === 'operator') {
      setActiveNavTab('camera-feed');
    } else if (role === 'supervisor') {
      setActiveNavTab('supervisor-analytics');
    } else {
      setActiveNavTab('overview');
    }
  }, []);

  const currentUser = userAccounts.find(u => u.role === currentRole) || userAccounts[0];

  const addToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const newToast: ToastMessage = { ...toast, id };
    setToasts(prev => [...prev, newToast]);

    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, toast.durationMs || 4500);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const refreshHealth = useCallback(async () => {
    const health = await healthService.checkHealth();
    setSystemHealth(health);
  }, []);

  useEffect(() => {
    let isMounted = true;
    healthService.checkHealth().then(health => {
      if (isMounted) {
        setSystemHealth(health);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const updateSystemSettings = useCallback((newSettings: Partial<SystemSettings>) => {
    setSystemSettings(prev => ({ ...prev, ...newSettings }));
    const newLog: SystemAuditLogEntry = {
      id: `AUDIT-SYS-${Date.now().toString().slice(-4)}`,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      actor: currentUser.name,
      actorRole: currentRole,
      eventCategory: 'SYSTEM_SETTING',
      description: `Updated enforcement parameters: ${Object.keys(newSettings).join(', ')}.`,
      ipAddress: '10.200.4.15'
    };
    setSystemAuditLogs(prev => [newLog, ...prev]);
    addToast({
      type: 'success',
      title: 'Enforcement Policy Updated',
      message: 'System parameters adjusted and logged to immutable audit trail.'
    });
  }, [currentUser.name, currentRole, addToast]);

  const addCameraSource = useCallback((newSource: CameraSourceRecord) => {
    setCameraSources(prev => [newSource, ...prev]);
    const newLog: SystemAuditLogEntry = {
      id: `AUDIT-SYS-${Date.now().toString().slice(-4)}`,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      actor: currentUser.name,
      actorRole: currentRole,
      eventCategory: 'CAMERA_CONFIG',
      description: `Registered new camera feed: ${newSource.name} (${newSource.junction}).`,
      ipAddress: '10.200.4.15'
    };
    setSystemAuditLogs(prev => [newLog, ...prev]);
    addToast({
      type: 'success',
      title: 'Camera Source Registered',
      message: `Enforcement stream ${newSource.name} added to active surveillance directory.`
    });
  }, [currentUser.name, currentRole, addToast]);

  // Reviewer actions
  const approveDraft = useCallback((caseId: string, reviewerNotes?: string) => {
    setCases(prev => prev.map(c => {
      if (c.id !== caseId) return c;
      const draftNumber = c.challanDraftNumber || `DFT-2026-${Math.floor(10000 + Math.random() * 90000)}`;
      return {
        ...c,
        status: 'DRAFT_CREATED',
        challanDraftNumber: draftNumber,
        draftAmountInr: c.draftAmountInr || 1000,
        reviewerNotes: reviewerNotes || c.reviewerNotes,
        reviewHistory: [
          {
            id: `audit-${Date.now()}`,
            timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
            actor: currentUser.name,
            role: currentRole,
            action: 'DRAFT_APPROVED',
            notes: reviewerNotes || 'Candidate draft approved for formal notice preparation. (No fine triggered yet)'
          },
          ...c.reviewHistory
        ]
      };
    }));

    const auditEntry: SystemAuditLogEntry = {
      id: `AUDIT-SYS-${Date.now().toString().slice(-4)}`,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      actor: currentUser.name,
      actorRole: currentRole,
      eventCategory: 'DRAFT_SANCTION',
      description: `Sanctioned review draft for case ${caseId} under Section 129 Motor Vehicles Act.`,
      ipAddress: '10.200.4.42'
    };
    setSystemAuditLogs(prev => [auditEntry, ...prev]);

    addToast({
      type: 'success',
      title: 'Challan Draft Created',
      message: `Case ${caseId} marked as draft. Note: This creates a review draft only and does not issue a fine.`
    });
  }, [currentUser.name, currentRole, addToast]);

  const rejectCase = useCallback((caseId: string, reason: string, notes?: string) => {
    setCases(prev => prev.map(c => {
      if (c.id !== caseId) return c;
      return {
        ...c,
        status: 'REJECTED',
        rejectionReason: reason,
        reviewerNotes: notes || c.reviewerNotes,
        reviewHistory: [
          {
            id: `audit-${Date.now()}`,
            timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
            actor: currentUser.name,
            role: currentRole,
            action: 'CASE_REJECTED',
            reason,
            notes: notes || `Case rejected: ${reason}`
          },
          ...c.reviewHistory
        ]
      };
    }));

    addToast({
      type: 'info',
      title: 'Case Rejected',
      message: `Case ${caseId} marked as rejected with reason: ${reason}.`
    });
  }, [currentUser.name, currentRole, addToast]);

  const addNewCapturedCase = useCallback((newCase: ViolationCase) => {
    setCases(prev => [newCase, ...prev]);
    addToast({
      type: 'success',
      title: 'Frame Ingested to Queue',
      message: `Candidate ${newCase.id} added to the Reviewer Queue.`
    });
  }, [addToast]);

  return (
    <AppContext.Provider
      value={{
        currentRole,
        setCurrentRole,
        currentUser,
        userAccounts,
        cases,
        setCases,
        persons,
        setPersons,
        cameraSources,
        setCameraSources,
        officerActivities,
        systemSettings,
        updateSystemSettings,
        systemAuditLogs,
        selectedCase,
        setSelectedCase,
        selectedPerson,
        setSelectedPerson,
        systemHealth,
        refreshHealth,
        toasts,
        addToast,
        removeToast,
        activeNavTab,
        setActiveNavTab,
        approveDraft,
        rejectCase,
        addNewCapturedCase,
        addCameraSource
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
