export type UserRole = 'admin' | 'reviewer' | 'operator' | 'supervisor';

export type ViolationStatus = 'PENDING_REVIEW' | 'DRAFT_CREATED' | 'REJECTED' | 'REVIEWED';

export type ViolationType = 
  | 'NO_HELMET_RIDER' 
  | 'NO_HELMET_PILLION' 
  | 'TRIPLE_RIDING' 
  | 'HELMET_STRAP_UNFASTENED';

export type CameraSourceType = 'WEBCAM' | 'IP_CAMERA' | 'CCTV_STREAM';

export type EvidenceQuality = 'HIGH' | 'MEDIUM' | 'LOW';

export type IdentityVerificationStatus = 'VERIFIED' | 'UNVERIFIED' | 'MANUAL_REQUIRED';

export interface BoundingBox {
  id: string;
  label: 'RIDER' | 'HELMET' | 'NO_HELMET' | 'LICENSE_PLATE' | 'MOTORCYCLE';
  confidence: number;
  x: number; // percentage (0 - 100)
  y: number;
  width: number;
  height: number;
  color: string;
}

export interface ReviewAuditLog {
  id: string;
  timestamp: string;
  actor: string;
  role: string;
  action: 'CREATED' | 'ASSIGNED' | 'NOTE_ADDED' | 'DRAFT_APPROVED' | 'CASE_REJECTED';
  notes?: string;
  reason?: string;
}

export interface LinkedPersonDetails {
  personId: string;
  fullName: string;
  maskedMobile: string;
  vehiclePlate: string;
  vehicleModel: string;
  identityVerified: boolean;
  registrationDate: string;
}

export interface ViolationCase {
  id: string;
  timestamp: string;
  camera: {
    id: string;
    name: string;
    location: string;
    type: CameraSourceType;
  };
  violationType: ViolationType;
  confidence: number;
  status: ViolationStatus;
  evidenceImageUrl: string;
  evidenceQuality: EvidenceQuality;
  boundingBoxes: BoundingBox[];
  linkedPerson?: LinkedPersonDetails;
  reviewerNotes?: string;
  reviewHistory: ReviewAuditLog[];
  challanDraftNumber?: string;
  draftAmountInr?: number;
  rejectionReason?: string;
}

export interface LinkedVehicle {
  plateNumber: string;
  vehicleType: string;
  model: string;
  registeredDate: string;
  status: 'ACTIVE' | 'EXPIRED' | 'FLAGGED';
}

export interface NotificationRecord {
  id: string;
  date: string;
  type: 'SMS' | 'EMAIL' | 'PORTAL';
  status: 'DELIVERED' | 'PENDING' | 'FAILED';
  title: string;
  preview: string;
}

export interface RegisteredPerson {
  personId: string;
  fullName: string;
  maskedMobile: string;
  email: string;
  city: string;
  identityStatus: IdentityVerificationStatus;
  linkedVehicles: LinkedVehicle[];
  notificationHistory: NotificationRecord[];
  linkedCasesCount: number;
}

export interface CameraSourceRecord {
  id: string;
  name: string;
  junction: string;
  streamType: CameraSourceType;
  status: 'ONLINE' | 'STANDBY' | 'DEGRADED' | 'OFFLINE';
  ipOrDeviceUrl: string;
  resolution: string;
  fps: number;
  dailyDetectionsCount: number;
  lastHeartbeat: string;
}

export interface OfficerActivity {
  officerId: string;
  officerName: string;
  rank: string;
  shift: string;
  totalReviewedToday: number;
  approvedDrafts: number;
  rejectedCount: number;
  avgReviewDurationSec: number;
  status: 'ON_DUTY' | 'ON_LEAVE' | 'BREAK';
}

export interface SystemSettings {
  minConfidenceThreshold: number;
  autoFlagPillionWithoutHelmet: boolean;
  autoFlagTripleRiding: boolean;
  requireSecondaryReviewForNightDetections: boolean;
  dataRetentionDays: number;
  defaultDraftPenaltyInr: number;
}

export interface SystemAuditLogEntry {
  id: string;
  timestamp: string;
  actor: string;
  actorRole: UserRole;
  eventCategory: 'ROLE_CHANGE' | 'CAMERA_CONFIG' | 'DRAFT_SANCTION' | 'SYSTEM_SETTING' | 'POLICY_UPDATE';
  description: string;
  ipAddress: string;
}

export interface SystemServiceHealth {
  status: 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'READY' | 'DEMO_STANDIN';
  responseTimeMs?: number;
  lastChecked: string;
  message?: string;
}

export interface SystemHealthState {
  api: SystemServiceHealth;
  database: SystemServiceHealth;
  model: SystemServiceHealth;
  camera: SystemServiceHealth;
  isBackendConnected: boolean;
  isDemoMode: boolean;
}

export interface HourlyStat {
  hour: string;
  detections: number;
  violations: number;
}

export interface MonthlyStat {
  month: string;
  totalDetections: number;
  approvedDrafts: number;
  rejected: number;
}

export interface DailyStat {
  date: string;
  detections: number;
  noHelmetCandidates: number;
  pendingReview: number;
  approvedDrafts: number;
  rejectedCases: number;
}

export interface DashboardStats {
  todayTotalDetections: number;
  todayNoHelmetCandidates: number;
  todayPendingReview: number;
  todayApprovedDrafts: number;
  todayRejectedCases: number;
  hourlyTrends: HourlyStat[];
  monthlyTrends: MonthlyStat[];
  dailyHistory: DailyStat[];
}

export interface UserAccount {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  department: string;
  status: 'ACTIVE' | 'INACTIVE';
  lastLogin: string;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  durationMs?: number;
}
