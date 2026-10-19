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
  label: 'RIDER' | 'HELMET' | 'NO_HELMET' | 'LICENSE_PLATE' | 'MOTORCYCLE' | string;
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
  riders?: RiderDetection[];
  plateMatch?: PlateMatchResult | null;
  riderCropUrl?: string | null;
  riderDetails?: {
    detectionId?: string;
    caseId?: string;
    classification?: string;
    helmetClass?: string;
    helmetConfidence?: number;
    confidence?: number;
    bbox?: [number, number, number, number];
    normalized?: [number, number, number, number];
    cropPath?: string | null;
    vehicleType?: string;
    vehicleConfidence?: number | null;
    vehicleBbox?: [number, number, number, number] | null;
    associationScore?: number;
    eligibleForChallan?: boolean;
    exclusionReason?: string | null;
    reviewStatus?: string;
  } | null;
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
  complianceRatePercent?: number;
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

export interface DetectionBox {
  id: string;
  label: string;
  classId: number;
  category: 'HELMET_VIOLATION' | 'HELMET_COMPLIANT' | 'PERSON' | 'VEHICLE' | 'OTHER' | string;
  confidence: number;
  xyxy: [number, number, number, number];
  normalized: [number, number, number, number];
  percentage: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  color: string;
}

export interface RiderDetection {
  detectionId: string;
  caseId?: string | null;
  label: string;
  classification: 'WITH_HELMET' | 'WITHOUT_HELMET' | 'UNKNOWN' | string;
  confidence: number;
  bbox: [number, number, number, number];
  normalized: [number, number, number, number];
  cropPath?: string | null;
  isViolation: boolean;
  vehicleType?: string;
  vehicleConfidence?: number | null;
  vehicleBbox?: [number, number, number, number] | null;
  associationScore?: number | null;
  eligibleForChallan?: boolean;
  exclusionReason?: string | null;
  helmetClass?: string | null;
  helmetConfidence?: number | null;
  reviewStatus?: string | null;
}

export interface PlateMatchResult {
  plateDetected: boolean;
  rawText?: string | null;
  normalizedPlate?: string | null;
  bbox?: [number, number, number, number] | null;
  cropPath?: string | null;
  matchStatus: 'VERIFIED' | 'UNVERIFIED' | 'MANUAL_REQUIRED' | string;
  matchSource?: string | null;
  confidence: number;
  matchedVehicleId?: string | null;
  matchedPersonId?: string | null;
  ownerNameSnapshot?: string | null;
  vehicleDetails?: Record<string, any> | null;
}

export interface IngestedCaseSummary {
  caseId: string;
  detectionId: string;
  violationType: ViolationType;
  confidence: number;
  cropPath?: string | null;
  status: string;
  bbox: [number, number, number, number];
  normalized: [number, number, number, number];
  isDeduplicated: boolean;
  vehicleType?: string;
  vehicleConfidence?: number | null;
  vehicleBbox?: [number, number, number, number] | null;
  associationScore?: number | null;
  eligibleForChallan?: boolean;
  exclusionReason?: string | null;
  reviewStatus?: string | null;
}

export interface DetectionAnalysisResult {
  detected: boolean;
  totalDetections: number;
  boxes: DetectionBox[];
  vehicles: DetectionBox[];
  persons: DetectionBox[];
  riders?: RiderDetection[];
  plateMatch?: PlateMatchResult | null;
  helmetClassificationAvailable: boolean;
  helmetClassificationMessage: string;
  isCandidateViolation: boolean;
  violationType?: ViolationType | null;
  violationConfidence?: number | null;
  caseId?: string | null;
  cases?: IngestedCaseSummary[];
  status: string;
  evidence?: {
    storagePath: string;
    fileHash?: string;
    mimeType?: string;
    width?: number;
    height?: number;
    fileSizeBytes?: number;
  };
  modelRunId?: string | null;
  processingTimeMs: number;
  imageDimensions: {
    width: number;
    height: number;
  };
  modelInfo: {
    provider?: string;
    isLoaded: boolean;
    modelPath?: string;
    modelId?: string;
    classesCount: number;
    helmetClassificationSupported: boolean;
    confidenceThreshold: number;
    loadError?: string | null;
    expectedClasses: string[];
  };
  isDeduplicated?: boolean;
  cooldownSecondsRemaining?: number | null;
}


