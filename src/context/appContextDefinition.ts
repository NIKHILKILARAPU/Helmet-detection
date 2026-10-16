import { createContext } from 'react';
import type { 
  UserRole, 
  ViolationCase, 
  ToastMessage, 
  SystemHealthState, 
  RegisteredPerson, 
  UserAccount 
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
}

export const AppContext = createContext<AppContextType | undefined>(undefined);
