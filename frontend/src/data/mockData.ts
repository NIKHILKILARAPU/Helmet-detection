import type { 
  ViolationCase, 
  RegisteredPerson, 
  UserAccount, 
  DashboardStats,
  SystemHealthState,
  CameraSourceRecord,
  OfficerActivity,
  SystemSettings,
  SystemAuditLogEntry
} from '../types';

export const INITIAL_REGISTERED_PERSONS: RegisteredPerson[] = [];

export const INITIAL_CASES: ViolationCase[] = [];

export const INITIAL_USER_ACCOUNTS: UserAccount[] = [];

export const INITIAL_CAMERA_SOURCES: CameraSourceRecord[] = [];

export const INITIAL_OFFICER_ACTIVITIES: OfficerActivity[] = [];

export const INITIAL_SYSTEM_SETTINGS: SystemSettings = {
  minConfidenceThreshold: 0.55,
  autoFlagPillionWithoutHelmet: true,
  autoFlagTripleRiding: true,
  requireSecondaryReviewForNightDetections: true,
  dataRetentionDays: 90,
  defaultDraftPenaltyInr: 1000
};

export const INITIAL_SYSTEM_AUDIT_LOGS: SystemAuditLogEntry[] = [];

export const INITIAL_DASHBOARD_STATS: DashboardStats = {
  todayTotalDetections: 0,
  todayNoHelmetCandidates: 0,
  todayPendingReview: 0,
  todayApprovedDrafts: 0,
  todayRejectedCases: 0,
  complianceRatePercent: 100.0,
  hourlyTrends: [],
  monthlyTrends: [],
  dailyHistory: []
};

export const INITIAL_SYSTEM_HEALTH: SystemHealthState = {
  api: { status: 'ONLINE', responseTimeMs: 12, lastChecked: 'Just now' },
  database: { status: 'ONLINE', responseTimeMs: 5, lastChecked: 'Just now' },
  model: { status: 'ONLINE', responseTimeMs: 45, lastChecked: 'Just now' },
  camera: { status: 'READY', lastChecked: 'Just now' },
  isBackendConnected: true,
  isDemoMode: false
};
