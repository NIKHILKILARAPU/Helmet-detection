import { createContext } from 'react';
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

export interface AppContextType {
  currentRole: UserRole;
  setCurrentRole: (role: UserRole) => void;
  currentUser: UserAccount;
  userAccounts: UserAccount[];
  cases: ViolationCase[];
  setCases: React.Dispatch<React.SetStateAction<ViolationCase[]>>;
  persons: RegisteredPerson[];
  setPersons: React.Dispatch<React.SetStateAction<RegisteredPerson[]>>;
  cameraSources: CameraSourceRecord[];
  setCameraSources: React.Dispatch<React.SetStateAction<CameraSourceRecord[]>>;
  officerActivities: OfficerActivity[];
  systemSettings: SystemSettings;
  updateSystemSettings: (newSettings: Partial<SystemSettings>) => void;
  systemAuditLogs: SystemAuditLogEntry[];
  selectedCase: ViolationCase | null;
  setSelectedCase: (caseItem: ViolationCase | null) => void;
  selectedPerson: RegisteredPerson | null;
  setSelectedPerson: (person: RegisteredPerson | null) => void;
  systemHealth: SystemHealthState;
  refreshHealth: () => Promise<void>;
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  activeNavTab: string;
  setActiveNavTab: (tab: string) => void;
  approveDraft: (caseId: string, reviewerNotes?: string) => void;
  rejectCase: (caseId: string, reason: string, notes?: string) => void;
  addNewCapturedCase: (newCase: ViolationCase) => void;
  addCameraSource: (newSource: CameraSourceRecord) => void;
  refreshAllData: () => Promise<void>;
}

export const AppContext = createContext<AppContextType | undefined>(undefined);
