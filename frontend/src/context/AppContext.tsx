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
import { healthService, INITIAL_SYSTEM_HEALTH_CLEAN } from '../services/healthService';
import { violationsService } from '../services/violationsService';
import { cameraService } from '../services/cameraService';
import { personService } from '../services/personService';
import { settingsService, DEFAULT_FRONTEND_SETTINGS } from '../services/settingsService';
import { operationsService } from '../services/operationsService';
import { AppContext } from './appContextDefinition';

const DEFAULT_ADMIN_ACCOUNT: UserAccount = {
  id: 'USR-ADMIN',
  name: 'Official Administrator',
  email: 'admin@trafficguard.gov.in',
  role: 'admin',
  department: 'Bengaluru Traffic Enforcement Directorate',
  status: 'ACTIVE',
  lastLogin: 'Active session'
};

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentRole, setCurrentRoleState] = useState<UserRole>('admin');
  const [userAccounts, setUserAccounts] = useState<UserAccount[]>([DEFAULT_ADMIN_ACCOUNT]);
  const [cases, setCases] = useState<ViolationCase[]>([]);
  const [persons, setPersons] = useState<RegisteredPerson[]>([]);
  const [cameraSources, setCameraSources] = useState<CameraSourceRecord[]>([]);
  const [officerActivities, setOfficerActivities] = useState<OfficerActivity[]>([]);
  const [systemSettings, setSystemSettings] = useState<SystemSettings>(DEFAULT_FRONTEND_SETTINGS);
  const [systemAuditLogs, setSystemAuditLogs] = useState<SystemAuditLogEntry[]>([]);
  const [selectedCase, setSelectedCase] = useState<ViolationCase | null>(null);
  const [selectedPerson, setSelectedPerson] = useState<RegisteredPerson | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealthState>(INITIAL_SYSTEM_HEALTH_CLEAN);
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

  const currentUser = userAccounts.find(u => u.role === currentRole) || {
    ...DEFAULT_ADMIN_ACCOUNT,
    role: currentRole,
    name: currentRole === 'operator' ? 'Duty Camera Operator' :
          currentRole === 'reviewer' ? 'Traffic Review Officer' :
          currentRole === 'supervisor' ? 'Supervisory Inspector' : 'Official Administrator'
  };

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

  const refreshAllData = useCallback(async () => {
    try {
      const [
        healthRes,
        casesRes,
        camerasRes,
        personsRes,
        usersRes,
        shiftsRes,
        auditRes,
        settingsRes
      ] = await Promise.allSettled([
        healthService.checkHealth(),
        violationsService.getCases(),
        cameraService.getCameras(),
        personService.getRegisteredPersons(),
        operationsService.getStaffUsers(),
        operationsService.getOfficerShifts(),
        settingsService.getAuditLogs(),
        settingsService.getSettings()
      ]);

      if (healthRes.status === 'fulfilled') {
        setSystemHealth(healthRes.value);
      }
      if (casesRes.status === 'fulfilled' && casesRes.value.cases) {
        setCases(casesRes.value.cases);
      }
      if (camerasRes.status === 'fulfilled' && camerasRes.value.cameras) {
        setCameraSources(camerasRes.value.cameras);
      }
      if (personsRes.status === 'fulfilled' && personsRes.value.persons) {
        setPersons(personsRes.value.persons);
      }
      if (usersRes.status === 'fulfilled' && usersRes.value.users.length > 0) {
        setUserAccounts(usersRes.value.users);
      }
      if (shiftsRes.status === 'fulfilled' && shiftsRes.value.shifts) {
        setOfficerActivities(shiftsRes.value.shifts);
      }
      if (auditRes.status === 'fulfilled' && auditRes.value.logs) {
        setSystemAuditLogs(auditRes.value.logs);
      }
      if (settingsRes.status === 'fulfilled' && settingsRes.value.settings) {
        setSystemSettings(settingsRes.value.settings);
      }
    } catch {
      // Ignore network errors on initial mount; specific services handle errors
    }
  }, []);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  const updateSystemSettings = useCallback(async (newSettings: Partial<SystemSettings>) => {
    try {
      const res = await settingsService.updateSettings(newSettings);
      if (res.success) {
        setSystemSettings(prev => ({ ...prev, ...newSettings }));
        addToast({
          type: 'success',
          title: 'Enforcement Policy Updated',
          message: 'System parameters adjusted and logged to immutable database audit trail.'
        });
        const auditRes = await settingsService.getAuditLogs();
        if (auditRes.success) {
          setSystemAuditLogs(auditRes.logs);
        }
      } else {
        addToast({
          type: 'error',
          title: 'Policy Update Failed',
          message: res.error || 'Server rejected settings update. Ensure you are authorized.'
        });
      }
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Policy Update Error',
        message: err.message || 'Network error updating settings.'
      });
    }
  }, [addToast]);

  const addCameraSource = useCallback(async (newSource: CameraSourceRecord) => {
    try {
      const res = await cameraService.registerCamera({
        name: newSource.name,
        junction: newSource.junction,
        streamType: newSource.streamType,
        ipOrDeviceUrl: newSource.ipOrDeviceUrl,
        resolution: newSource.resolution,
        fps: newSource.fps
      });

      if (res.success && res.camera) {
        setCameraSources(prev => [res.camera!, ...prev]);
        addToast({
          type: 'success',
          title: 'Camera Source Registered',
          message: `Enforcement stream ${res.camera.name} registered in database.`
        });
        const auditRes = await settingsService.getAuditLogs();
        if (auditRes.success) {
          setSystemAuditLogs(auditRes.logs);
        }
      } else {
        addToast({
          type: 'error',
          title: 'Camera Registration Failed',
          message: res.error || 'Database rejected camera registration.'
        });
      }
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Camera Registration Error',
        message: err.message || 'Network error registering camera.'
      });
    }
  }, [addToast]);

  // Reviewer actions with real backend endpoints
  const approveDraft = useCallback(async (caseId: string, reviewerNotes?: string) => {
    try {
      const res = await violationsService.approveDraft(caseId, currentUser.name, reviewerNotes);
      if (res.success && res.updatedCase) {
        setCases(prev => prev.map(c => c.id === caseId ? res.updatedCase : c));
        addToast({
          type: 'success',
          title: 'Challan Draft Created',
          message: `Case ${caseId} marked as draft in database. Note: Review draft only (no fine automatically triggered).`
        });
        const auditRes = await settingsService.getAuditLogs();
        if (auditRes.success) {
          setSystemAuditLogs(auditRes.logs);
        }
      }
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Draft Approval Failed',
        message: err.message || 'Could not approve case draft on server.'
      });
    }
  }, [currentUser.name, addToast]);

  const rejectCase = useCallback(async (caseId: string, reason: string, notes?: string) => {
    try {
      const res = await violationsService.rejectCase(caseId, currentUser.name, reason, notes);
      if (res.success && res.updatedCase) {
        setCases(prev => prev.map(c => c.id === caseId ? res.updatedCase : c));
        addToast({
          type: 'info',
          title: 'Case Rejected',
          message: `Case ${caseId} marked as rejected in database with reason: ${reason}.`
        });
        const auditRes = await settingsService.getAuditLogs();
        if (auditRes.success) {
          setSystemAuditLogs(auditRes.logs);
        }
      }
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Case Rejection Failed',
        message: err.message || 'Could not reject case on server.'
      });
    }
  }, [currentUser.name, addToast]);

  const addNewCapturedCase = useCallback((newCase: ViolationCase) => {
    setCases(prev => [newCase, ...prev.filter(c => c.id !== newCase.id)]);
    addToast({
      type: 'success',
      title: 'Candidate Ingested to Database',
      message: `Candidate ${newCase.id} saved as PENDING_REVIEW in queue.`
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
        addCameraSource,
        refreshAllData
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
