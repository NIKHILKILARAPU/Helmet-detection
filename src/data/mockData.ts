import type { 
  ViolationCase, 
  RegisteredPerson, 
  UserAccount, 
  DashboardStats,
  SystemHealthState 
} from '../types';

// Helper to generate SVG data URIs for realistic offline evidence images
export const generateTrafficEvidenceSvg = (type: 'NO_HELMET' | 'HELMET_SAFE' | 'TRIPLE', caseId: string): string => {
  const isNoHelmet = type === 'NO_HELMET' || type === 'TRIPLE';
  const riderHeadColor = isNoHelmet ? '#EF4444' : '#10B981';
  const labelText = isNoHelmet ? 'CANDIDATE: NO HELMET' : 'HELMET VERIFIED';

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400" width="100%" height="100%">
    <defs>
      <linearGradient id="road" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#334155" />
        <stop offset="100%" stop-color="#1E293B" />
      </linearGradient>
      <linearGradient id="sky" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#64748B" />
        <stop offset="100%" stop-color="#475569" />
      </linearGradient>
    </defs>
    <!-- Background: Sky & Road -->
    <rect width="640" height="200" fill="url(#sky)" />
    <rect y="180" width="640" height="220" fill="url(#road)" />
    <!-- Distant buildings silhouette -->
    <path d="M 0 180 L 40 140 L 70 140 L 90 180 L 150 120 L 210 120 L 230 180 L 400 130 L 440 180 L 640 160 L 640 180 Z" fill="#1e293b" opacity="0.6" />
    
    <!-- Road Lane markings -->
    <line x1="120" y1="400" x2="260" y2="180" stroke="#F8FAFC" stroke-width="4" stroke-dasharray="25,20" opacity="0.7" />
    <line x1="520" y1="400" x2="380" y2="180" stroke="#F8FAFC" stroke-width="4" stroke-dasharray="25,20" opacity="0.7" />
    <line x1="320" y1="400" x2="320" y2="200" stroke="#F59E0B" stroke-width="4" stroke-dasharray="30,15" opacity="0.8" />
    
    <!-- Camera Timestamp HUD Overlay -->
    <rect x="15" y="15" width="280" height="32" rx="4" fill="#000000" opacity="0.7" />
    <text x="25" y="36" fill="#10B981" font-family="monospace" font-size="13" font-weight="bold">CAM-04 [JUNCTION 4] LIVE</text>
    <text x="25" y="58" fill="#F8FAFC" font-family="monospace" font-size="11">CASE: ${caseId}</text>

    <!-- Motorcycle and Rider Graphics -->
    <g transform="translate(240, 90)">
      <!-- Motorcycle Body -->
      <path d="M 30 210 L 80 180 L 110 200 L 130 170 L 150 210 Z" fill="#0284C7" />
      <!-- Wheels -->
      <circle cx="20" cy="220" r="28" fill="#0F172A" stroke="#94A3B8" stroke-width="6" />
      <circle cx="140" cy="220" r="28" fill="#0F172A" stroke="#94A3B8" stroke-width="6" />
      <!-- Handlebar -->
      <line x1="95" y1="140" x2="125" y2="140" stroke="#CBD5E1" stroke-width="6" stroke-linecap="round" />
      <line x1="110" y1="140" x2="120" y2="180" stroke="#64748B" stroke-width="6" />

      <!-- Rider Body -->
      <path d="M 60 160 L 80 110 L 110 145 Z" fill="#334155" />
      <!-- Rider Head / Helmet Area -->
      <circle cx="80" cy="85" r="22" fill="${riderHeadColor}" />
      ${isNoHelmet ? `
        <!-- Unprotected Head Hair/Facial contour -->
        <circle cx="80" cy="85" r="18" fill="#D97706" />
        <path d="M 65 80 Q 80 65 95 80" stroke="#1F2937" stroke-width="6" fill="none" />
      ` : `
        <!-- Full Face Safety Helmet -->
        <path d="M 62 82 Q 80 60 98 82 Q 95 105 78 105 Q 64 100 62 82" fill="#047857" />
        <rect x="74" y="80" width="22" height="12" rx="3" fill="#111827" />
      `}

      <!-- License Plate Box -->
      <g transform="translate(130, 210)">
        <rect width="60" height="22" rx="3" fill="#FEF08A" stroke="#1E293B" stroke-width="2" />
        <text x="6" y="15" fill="#1E293B" font-family="monospace" font-size="10" font-weight="bold">KA01MJ4892</text>
      </g>
    </g>

    <!-- AI Bounding Box Graphic Overlay -->
    <g transform="translate(290, 140)">
      <rect x="0" y="0" width="65" height="65" rx="2" fill="none" stroke="${riderHeadColor}" stroke-width="3" stroke-dasharray="6,4" />
      <rect x="0" y="-22" width="140" height="22" fill="${riderHeadColor}" />
      <text x="6" y="-7" fill="#FFFFFF" font-family="sans-serif" font-size="10" font-weight="bold">${labelText}</text>
    </g>

    <!-- License Plate Detection Box -->
    <g transform="translate(365, 295)">
      <rect x="0" y="0" width="70" height="28" rx="2" fill="none" stroke="#2563EB" stroke-width="2" />
      <rect x="0" y="-18" width="55" height="18" fill="#2563EB" />
      <text x="4" y="-5" fill="#FFFFFF" font-family="sans-serif" font-size="9" font-weight="bold">PLATE 96%</text>
    </g>
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

export const INITIAL_REGISTERED_PERSONS: RegisteredPerson[] = [
  {
    personId: 'PID-77319',
    fullName: 'Aditya Sharma',
    maskedMobile: '+91 98*** **412',
    email: 'a.sharma.demo@trafficguard.local',
    city: 'Bengaluru, Karnataka',
    identityStatus: 'VERIFIED',
    linkedCasesCount: 2,
    linkedVehicles: [
      {
        plateNumber: 'KA 01 MJ 4892',
        vehicleType: 'Two-Wheeler (Motorcycle)',
        model: 'Honda Activa 6G - Matte Axis Grey',
        registeredDate: '2023-04-12',
        status: 'ACTIVE'
      },
      {
        plateNumber: 'KA 03 EX 1099',
        vehicleType: 'Two-Wheeler (Scooter)',
        model: 'TVS Jupiter 125',
        registeredDate: '2022-09-18',
        status: 'ACTIVE'
      }
    ],
    notificationHistory: [
      {
        id: 'NOTIF-901',
        date: '2026-10-15 14:32',
        type: 'SMS',
        status: 'DELIVERED',
        title: 'Draft Challan Observation Notice',
        preview: 'Traffic observation TG-2026-8941 recorded near Koramangala Jn. A human-reviewed draft is under review. Visit portal for details.'
      },
      {
        id: 'NOTIF-890',
        date: '2026-09-28 11:15',
        type: 'PORTAL',
        status: 'DELIVERED',
        title: 'Annual Registration Verified',
        preview: 'Vehicle KA 01 MJ 4892 verified with state transport database.'
      }
    ]
  },
  {
    personId: 'PID-63402',
    fullName: 'Priya Nandakumar Patel',
    maskedMobile: '+91 94*** **870',
    email: 'p.patel.demo@trafficguard.local',
    city: 'Bengaluru, Karnataka',
    identityStatus: 'VERIFIED',
    linkedCasesCount: 1,
    linkedVehicles: [
      {
        plateNumber: 'KA 05 HL 8310',
        vehicleType: 'Two-Wheeler (Motorcycle)',
        model: 'Yamaha FZ-S FI 150cc',
        registeredDate: '2024-01-10',
        status: 'ACTIVE'
      }
    ],
    notificationHistory: [
      {
        id: 'NOTIF-855',
        date: '2026-10-14 09:20',
        type: 'SMS',
        status: 'DELIVERED',
        title: 'Review Queue Notification',
        preview: 'Candidate safety alert TG-2026-8938 generated. Human review pending.'
      }
    ]
  },
  {
    personId: 'PID-51288',
    fullName: 'Rajesh G. Rao',
    maskedMobile: '+91 91*** **239',
    email: 'r.rao.demo@trafficguard.local',
    city: 'Bengaluru, Karnataka',
    identityStatus: 'MANUAL_REQUIRED',
    linkedCasesCount: 1,
    linkedVehicles: [
      {
        plateNumber: 'KA 04 QA 9021',
        vehicleType: 'Two-Wheeler (Motorcycle)',
        model: 'Royal Enfield Classic 350',
        registeredDate: '2021-11-05',
        status: 'FLAGGED'
      }
    ],
    notificationHistory: [
      {
        id: 'NOTIF-790',
        date: '2026-10-12 16:40',
        type: 'EMAIL',
        status: 'DELIVERED',
        title: 'Document Update Required',
        preview: 'Vehicle insurance and ownership record requires re-validation in state registry.'
      }
    ]
  },
  {
    personId: 'PID-90432',
    fullName: 'Sneha K. Varma',
    maskedMobile: '+91 97*** **651',
    email: 's.varma.demo@trafficguard.local',
    city: 'Bengaluru, Karnataka',
    identityStatus: 'VERIFIED',
    linkedCasesCount: 0,
    linkedVehicles: [
      {
        plateNumber: 'KA 51 TR 6722',
        vehicleType: 'Two-Wheeler (Scooter)',
        model: 'Ather 450X Gen 3',
        registeredDate: '2023-08-14',
        status: 'ACTIVE'
      }
    ],
    notificationHistory: []
  }
];

export const INITIAL_CASES: ViolationCase[] = [
  {
    id: 'TG-2026-8941',
    timestamp: '2026-10-16 11:42:18',
    camera: {
      id: 'CAM-BLR-04',
      name: 'Koramangala 80ft Road Junction',
      location: 'South Bound, Lane 2',
      type: 'CCTV_STREAM'
    },
    violationType: 'NO_HELMET_RIDER',
    confidence: 0.94,
    status: 'PENDING_REVIEW',
    evidenceImageUrl: generateTrafficEvidenceSvg('NO_HELMET', 'TG-2026-8941'),
    evidenceQuality: 'HIGH',
    boundingBoxes: [
      {
        id: 'bb-1',
        label: 'NO_HELMET',
        confidence: 0.94,
        x: 45,
        y: 35,
        width: 12,
        height: 16,
        color: '#DC2626'
      },
      {
        id: 'bb-2',
        label: 'RIDER',
        confidence: 0.96,
        x: 40,
        y: 28,
        width: 24,
        height: 48,
        color: '#2563EB'
      },
      {
        id: 'bb-3',
        label: 'LICENSE_PLATE',
        confidence: 0.92,
        x: 57,
        y: 72,
        width: 11,
        height: 7,
        color: '#F59E0B'
      }
    ],
    linkedPerson: {
      personId: 'PID-77319',
      fullName: 'Aditya Sharma',
      maskedMobile: '+91 98*** **412',
      vehiclePlate: 'KA 01 MJ 4892',
      vehicleModel: 'Honda Activa 6G',
      identityVerified: true,
      registrationDate: '2023-04-12'
    },
    reviewerNotes: '',
    reviewHistory: [
      {
        id: 'audit-1',
        timestamp: '2026-10-16 11:42:19',
        actor: 'AI Edge Ingestion',
        role: 'system',
        action: 'CREATED',
        notes: 'High confidence candidate detection flagged by YOLOv8 Traffic Guard worker.'
      }
    ]
  },
  {
    id: 'TG-2026-8940',
    timestamp: '2026-10-16 11:15:02',
    camera: {
      id: 'CAM-BLR-01',
      name: 'MG Road Trinity Circle',
      location: 'East Bound, Lane 1',
      type: 'IP_CAMERA'
    },
    violationType: 'NO_HELMET_PILLION',
    confidence: 0.89,
    status: 'DRAFT_CREATED',
    evidenceImageUrl: generateTrafficEvidenceSvg('TRIPLE', 'TG-2026-8940'),
    evidenceQuality: 'HIGH',
    challanDraftNumber: 'DFT-2026-00481',
    draftAmountInr: 1000,
    boundingBoxes: [
      {
        id: 'bb-4',
        label: 'NO_HELMET',
        confidence: 0.89,
        x: 48,
        y: 38,
        width: 10,
        height: 14,
        color: '#DC2626'
      },
      {
        id: 'bb-5',
        label: 'HELMET',
        confidence: 0.95,
        x: 39,
        y: 32,
        width: 11,
        height: 15,
        color: '#15803D'
      }
    ],
    linkedPerson: {
      personId: 'PID-63402',
      fullName: 'Priya Nandakumar Patel',
      maskedMobile: '+91 94*** **870',
      vehiclePlate: 'KA 05 HL 8310',
      vehicleModel: 'Yamaha FZ-S FI 150cc',
      identityVerified: true,
      registrationDate: '2024-01-10'
    },
    reviewerNotes: 'Clear visual confirmation: Rider wore full-face helmet, but rear pillion passenger was unhelmeted.',
    reviewHistory: [
      {
        id: 'audit-2',
        timestamp: '2026-10-16 11:15:03',
        actor: 'AI Edge Ingestion',
        role: 'system',
        action: 'CREATED',
        notes: 'Dual rider detection frame ingested.'
      },
      {
        id: 'audit-3',
        timestamp: '2026-10-16 11:28:40',
        actor: 'Insp. R. Deshmukh',
        role: 'reviewer',
        action: 'DRAFT_APPROVED',
        notes: 'Challan draft created for pillion safety compliance review under Section 129 Motor Vehicles Act.'
      }
    ]
  },
  {
    id: 'TG-2026-8939',
    timestamp: '2026-10-16 10:48:33',
    camera: {
      id: 'CAM-BLR-02',
      name: 'Indiranagar 100ft Road',
      location: 'North Bound, Lane 3',
      type: 'CCTV_STREAM'
    },
    violationType: 'HELMET_STRAP_UNFASTENED',
    confidence: 0.61,
    status: 'REJECTED',
    evidenceImageUrl: generateTrafficEvidenceSvg('HELMET_SAFE', 'TG-2026-8939'),
    evidenceQuality: 'LOW',
    rejectionReason: 'Shadow interference caused false positive on helmet chin strap; rider is wearing compliant gear.',
    boundingBoxes: [
      {
        id: 'bb-6',
        label: 'HELMET',
        confidence: 0.61,
        x: 44,
        y: 33,
        width: 12,
        height: 15,
        color: '#F59E0B'
      }
    ],
    linkedPerson: {
      personId: 'PID-51288',
      fullName: 'Rajesh G. Rao',
      maskedMobile: '+91 91*** **239',
      vehiclePlate: 'KA 04 QA 9021',
      vehicleModel: 'Royal Enfield Classic 350',
      identityVerified: false,
      registrationDate: '2021-11-05'
    },
    reviewerNotes: 'Upon close inspection at high resolution, rider is wearing a dark half-face helmet with secured strap. Low lighting in underpass created shadow illusion.',
    reviewHistory: [
      {
        id: 'audit-4',
        timestamp: '2026-10-16 10:48:35',
        actor: 'AI Edge Ingestion',
        role: 'system',
        action: 'CREATED'
      },
      {
        id: 'audit-5',
        timestamp: '2026-10-16 11:02:15',
        actor: 'Insp. R. Deshmukh',
        role: 'reviewer',
        action: 'CASE_REJECTED',
        reason: 'Low quality evidence & false shadow trigger. Compliant helmet verified.'
      }
    ]
  },
  {
    id: 'TG-2026-8938',
    timestamp: '2026-10-16 09:12:44',
    camera: {
      id: 'CAM-BLR-04',
      name: 'Koramangala 80ft Road Junction',
      location: 'South Bound, Lane 1',
      type: 'CCTV_STREAM'
    },
    violationType: 'TRIPLE_RIDING',
    confidence: 0.91,
    status: 'REVIEWED',
    evidenceImageUrl: generateTrafficEvidenceSvg('TRIPLE', 'TG-2026-8938'),
    evidenceQuality: 'HIGH',
    challanDraftNumber: 'DFT-2026-00479',
    draftAmountInr: 2000,
    boundingBoxes: [
      {
        id: 'bb-7',
        label: 'NO_HELMET',
        confidence: 0.91,
        x: 42,
        y: 34,
        width: 14,
        height: 18,
        color: '#DC2626'
      }
    ],
    linkedPerson: {
      personId: 'PID-77319',
      fullName: 'Aditya Sharma',
      maskedMobile: '+91 98*** **412',
      vehiclePlate: 'KA 01 MJ 4892',
      vehicleModel: 'Honda Activa 6G',
      identityVerified: true,
      registrationDate: '2023-04-12'
    },
    reviewerNotes: 'Three occupants on two-wheeler; 2 occupants without helmets. Case verified and transferred to notice dispatch queue.',
    reviewHistory: [
      {
        id: 'audit-6',
        timestamp: '2026-10-16 09:12:45',
        actor: 'AI Edge Ingestion',
        role: 'system',
        action: 'CREATED'
      },
      {
        id: 'audit-7',
        timestamp: '2026-10-16 09:40:00',
        actor: 'Senior Reviewer A. Sen',
        role: 'reviewer',
        action: 'DRAFT_APPROVED',
        notes: 'Triple riding safety violation confirmed.'
      }
    ]
  },
  {
    id: 'TG-2026-8937',
    timestamp: '2026-10-16 08:35:10',
    camera: {
      id: 'CAM-BLR-03',
      name: 'Hebbal Flyover North Ramp',
      location: 'North Bound, Lane 2',
      type: 'IP_CAMERA'
    },
    violationType: 'NO_HELMET_RIDER',
    confidence: 0.97,
    status: 'PENDING_REVIEW',
    evidenceImageUrl: generateTrafficEvidenceSvg('NO_HELMET', 'TG-2026-8937'),
    evidenceQuality: 'HIGH',
    boundingBoxes: [
      {
        id: 'bb-8',
        label: 'NO_HELMET',
        confidence: 0.97,
        x: 46,
        y: 33,
        width: 12,
        height: 16,
        color: '#DC2626'
      }
    ],
    reviewerNotes: '',
    reviewHistory: [
      {
        id: 'audit-8',
        timestamp: '2026-10-16 08:35:11',
        actor: 'AI Edge Ingestion',
        role: 'system',
        action: 'CREATED',
        notes: 'Automated frame capture at 48 km/h.'
      }
    ]
  }
];

export const INITIAL_USER_ACCOUNTS: UserAccount[] = [
  {
    id: 'USR-001',
    name: 'Inspector Vikram Malhotra',
    email: 'v.malhotra@trafficpolice.gov.in',
    role: 'admin',
    department: 'Central Traffic Enforcement Cell',
    status: 'ACTIVE',
    lastLogin: '2026-10-16 11:30'
  },
  {
    id: 'USR-002',
    name: 'Sub-Inspector Rohit Deshmukh',
    email: 'r.deshmukh@trafficpolice.gov.in',
    role: 'reviewer',
    department: 'Violation Review & Notice Unit',
    status: 'ACTIVE',
    lastLogin: '2026-10-16 11:25'
  },
  {
    id: 'USR-003',
    name: 'Operator Ananya Joshi',
    email: 'a.joshi@trafficcontrol.local',
    role: 'operator',
    department: 'CCTV Surveillance & Camera Operations',
    status: 'ACTIVE',
    lastLogin: '2026-10-16 10:10'
  },
  {
    id: 'USR-004',
    name: 'Aditya Sharma (Registered Citizen)',
    email: 'aditya.sharma@example.com',
    role: 'citizen',
    department: 'Public Citizen Portal',
    status: 'ACTIVE',
    lastLogin: '2026-10-16 09:05'
  }
];

export const INITIAL_DASHBOARD_STATS: DashboardStats = {
  todayTotalDetections: 1428,
  todayNoHelmetCandidates: 87,
  todayPendingReview: 14,
  todayApprovedDrafts: 58,
  todayRejectedCases: 15,
  hourlyTrends: [
    { hour: '06:00', detections: 42, violations: 3 },
    { hour: '07:00', detections: 98, violations: 8 },
    { hour: '08:00', detections: 195, violations: 16 },
    { hour: '09:00', detections: 284, violations: 22 },
    { hour: '10:00', detections: 240, violations: 17 },
    { hour: '11:00', detections: 180, violations: 12 },
    { hour: '12:00', detections: 145, violations: 9 }
  ],
  monthlyTrends: [
    { month: 'May 2026', totalDetections: 28400, approvedDrafts: 1420, rejected: 310 },
    { month: 'Jun 2026', totalDetections: 31200, approvedDrafts: 1580, rejected: 295 },
    { month: 'Jul 2026', totalDetections: 34100, approvedDrafts: 1740, rejected: 340 },
    { month: 'Aug 2026', totalDetections: 32900, approvedDrafts: 1610, rejected: 280 },
    { month: 'Sep 2026', totalDetections: 36800, approvedDrafts: 1890, rejected: 365 },
    { month: 'Oct 2026', totalDetections: 19400, approvedDrafts: 920, rejected: 185 }
  ],
  dailyHistory: [
    { date: '2026-10-10', detections: 1380, noHelmetCandidates: 79, pendingReview: 0, approvedDrafts: 64, rejectedCases: 15 },
    { date: '2026-10-11', detections: 1420, noHelmetCandidates: 84, pendingReview: 0, approvedDrafts: 70, rejectedCases: 14 },
    { date: '2026-10-12', detections: 1510, noHelmetCandidates: 92, pendingReview: 0, approvedDrafts: 78, rejectedCases: 14 },
    { date: '2026-10-13', detections: 1490, noHelmetCandidates: 88, pendingReview: 0, approvedDrafts: 72, rejectedCases: 16 },
    { date: '2026-10-14', detections: 1610, noHelmetCandidates: 96, pendingReview: 0, approvedDrafts: 81, rejectedCases: 15 },
    { date: '2026-10-15', detections: 1580, noHelmetCandidates: 91, pendingReview: 2, approvedDrafts: 75, rejectedCases: 14 },
    { date: '2026-10-16', detections: 1428, noHelmetCandidates: 87, pendingReview: 14, approvedDrafts: 58, rejectedCases: 15 }
  ]
};

export const INITIAL_SYSTEM_HEALTH: SystemHealthState = {
  api: {
    status: 'ONLINE',
    responseTimeMs: 24,
    lastChecked: 'Just now',
    message: 'FastAPI service reachable (simulation ready)'
  },
  database: {
    status: 'ONLINE',
    responseTimeMs: 12,
    lastChecked: 'Just now',
    message: 'MongoDB instance active (replica set healthy)'
  },
  model: {
    status: 'DEMO_STANDIN',
    responseTimeMs: 85,
    lastChecked: 'Just now',
    message: 'YOLOv8 Helmet Detection Engine: Demo simulation boundary active'
  },
  camera: {
    status: 'ONLINE',
    responseTimeMs: 16,
    lastChecked: 'Just now',
    message: '4 camera streams configured; laptop webcam standby'
  },
  isBackendConnected: false,
  isDemoMode: true
};
