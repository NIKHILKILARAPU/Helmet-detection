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
