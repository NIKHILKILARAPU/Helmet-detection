import type { ViolationCase, ViolationStatus, ViolationType, ReviewAuditLog, BoundingBox } from '../types';
import { apiClient, getMediaUrl } from './api';

export interface ViolationFilters {
  status?: ViolationStatus | 'ALL';
  violationType?: ViolationType | 'ALL';
  searchQuery?: string;
  dateFrom?: string;
  dateTo?: string;
}

export function mapBackendViolationToCase(doc: any): ViolationCase {
  const id = doc.caseId || doc.id || (doc._id ? String(doc._id) : 'UNKNOWN');
  const capturedAt = doc.capturedAt 
    ? new Date(doc.capturedAt).toISOString().replace('T', ' ').substring(0, 19) 
    : new Date().toISOString().replace('T', ' ').substring(0, 19);

  const rawEvidencePath = doc.evidence?.storagePath || doc.evidence?.imageUrl || doc.evidenceImageUrl || '';
  const evidenceImageUrl = getMediaUrl(rawEvidencePath);

  const rawRiderCropPath = doc.evidence?.riderCropPath || doc.riderDetails?.cropPath || '';
  const riderCropUrl = rawRiderCropPath ? getMediaUrl(rawRiderCropPath) : null;

  const camera = typeof doc.camera === 'object' && doc.camera !== null ? {
    id: doc.camera.id || String(doc.cameraId || 'CAM-01'),
    name: doc.camera.name || doc.cameraName || 'Traffic Station',
    location: doc.camera.location || doc.junction || 'Roadside Junction',
    type: doc.camera.type || 'WEBCAM'
  } : {
    id: String(doc.cameraId || 'CAM-01'),
    name: doc.cameraName || 'Traffic Station',
    location: doc.junction || 'Roadside Junction',
    type: 'WEBCAM' as const
  };

  const boundingBoxes: BoundingBox[] = Array.isArray(doc.boundingBoxes) ? doc.boundingBoxes.map((b: any, idx: number) => {
    let x = 0, y = 0, width = 0, height = 0;
    if (b.x !== undefined && b.width !== undefined) {
      x = b.x;
      y = b.y ?? 0;
      width = b.width;
      height = b.height ?? 0;
    } else if (b.coordinates) {
      if (Array.isArray(b.coordinates) && b.coordinates.length >= 4) {
        const [x1, y1, x2, y2] = b.coordinates;
        x = x1 * 100;
        y = y1 * 100;
        width = Math.max(0, (x2 - x1) * 100);
        height = Math.max(0, (y2 - y1) * 100);
      } else if (typeof b.coordinates === 'object') {
        const x1 = b.coordinates.x1 ?? b.coordinates.xmin ?? 0;
        const y1 = b.coordinates.y1 ?? b.coordinates.ymin ?? 0;
        const x2 = b.coordinates.x2 ?? b.coordinates.xmax ?? 0;
        const y2 = b.coordinates.y2 ?? b.coordinates.ymax ?? 0;
        x = x1 * 100;
        y = y1 * 100;
        width = Math.max(0, (x2 - x1) * 100);
        height = Math.max(0, (y2 - y1) * 100);
      }
    } else if (doc.riderDetails?.normalized && Array.isArray(doc.riderDetails.normalized) && doc.riderDetails.normalized.length >= 4) {
      const [x1, y1, x2, y2] = doc.riderDetails.normalized;
      x = x1 * 100;
      y = y1 * 100;
      width = Math.max(0, (x2 - x1) * 100);
      height = Math.max(0, (y2 - y1) * 100);
    }

    const label = b.className || b.label || 'Without Helmet';
    const isViolation = label === 'Without Helmet' || label === 'NO_HELMET' || label === 'NO_HELMET_RIDER';

    return {
      id: b.id || `bb-${idx}`,
      label: label as any,
      confidence: b.confidence ?? doc.confidence ?? 0.9,
      x,
      y,
      width,
      height,
      color: b.color || (isViolation ? '#DC2626' : '#15803D')
    };
  }) : [];

  if (boundingBoxes.length === 0 && doc.riderDetails?.normalized && Array.isArray(doc.riderDetails.normalized) && doc.riderDetails.normalized.length >= 4) {
    const [x1, y1, x2, y2] = doc.riderDetails.normalized;
    boundingBoxes.push({
      id: `bb-rider-${id}`,
      label: (doc.riderDetails.classification === 'WITH_HELMET' ? 'With Helmet' : 'Without Helmet') as any,
      confidence: doc.riderDetails.confidence ?? doc.confidence ?? 0.9,
      x: x1 * 100,
      y: y1 * 100,
      width: Math.max(0, (x2 - x1) * 100),
      height: Math.max(0, (y2 - y1) * 100),
      color: doc.riderDetails.classification === 'WITH_HELMET' ? '#15803D' : '#DC2626'
    });
  }

  const reviewHistory: ReviewAuditLog[] = Array.isArray(doc.reviewHistory) && doc.reviewHistory.length > 0 
    ? doc.reviewHistory 
    : (doc.reviewedBy ? [{
        id: `audit-${doc.reviewedAt || Date.now()}`,
        timestamp: doc.reviewedAt ? new Date(doc.reviewedAt).toISOString().replace('T', ' ').substring(0, 19) : capturedAt,
        actor: String(doc.reviewedBy),
        role: 'reviewer',
        action: (doc.status === 'REJECTED' ? 'CASE_REJECTED' : 'DRAFT_APPROVED') as any,
        notes: doc.reviewerNotes,
        reason: doc.rejectionReason
      }] : []);

  return {
    id,
    timestamp: capturedAt,
    camera,
    violationType: doc.violationType || 'NO_HELMET_RIDER',
    confidence: doc.confidence ?? 0.9,
    status: (doc.status as ViolationStatus) || 'PENDING_REVIEW',
    evidenceImageUrl,
    evidenceQuality: doc.evidenceQuality || 'HIGH',
    boundingBoxes,
    linkedPerson: doc.linkedPerson,
    reviewerNotes: doc.reviewerNotes,
    reviewHistory,
    challanDraftNumber: doc.challanDraftNumber,
    draftAmountInr: doc.draftAmountInr,
    rejectionReason: doc.rejectionReason,
    riders: doc.riders,
    plateMatch: doc.plateMatch,
    riderCropUrl,
    riderDetails: doc.riderDetails || null
  };
}

class ViolationsService {
  async getCases(filters?: ViolationFilters): Promise<{ cases: ViolationCase[]; isDemo: boolean; error?: string }> {
    const params = new URLSearchParams();
    if (filters?.status && filters.status !== 'ALL') {
      params.append('status', filters.status);
    }
    if (filters?.violationType && filters.violationType !== 'ALL') {
      params.append('type', filters.violationType);
    }
    if (filters?.searchQuery && filters.searchQuery.trim()) {
      params.append('search', filters.searchQuery.trim());
    }

    const queryStr = params.toString() ? `?${params.toString()}` : '';
    const res = await apiClient.get<any[]>(`/violations${queryStr}`);

    if (!res.success || !res.data) {
      return {
        cases: [],
        isDemo: false,
        error: res.error || 'Failed to retrieve violations from database.'
      };
    }

    const rawList = Array.isArray(res.data) ? res.data : [];
    const cases = rawList.map(mapBackendViolationToCase);

    return {
      cases,
      isDemo: false
    };
  }

  async getCaseById(caseId: string): Promise<ViolationCase | null> {
    const res = await apiClient.get<any>(`/violations/${encodeURIComponent(caseId)}`);
    if (!res.success || !res.data) {
      return null;
    }
    return mapBackendViolationToCase(res.data);
  }

  async approveDraft(
    caseId: string, 
    reviewerName: string, 
    notes?: string
  ): Promise<{ success: boolean; updatedCase: ViolationCase; isDemo: boolean }> {
    const res = await apiClient.post<any>(`/violations/${encodeURIComponent(caseId)}/approve-draft`, {
      reviewerName,
      notes: notes || undefined
    });

    if (!res.success || !res.data) {
      throw new Error(res.error || `Failed to approve draft for case ${caseId}`);
    }

    // Fetch fresh full case document from database to preserve all evidence, crops, and metadata
    const freshCase = await this.getCaseById(caseId);

    return {
      success: true,
      updatedCase: freshCase || mapBackendViolationToCase(res.data),
      isDemo: false
    };
  }

  async rejectCase(
    caseId: string, 
    reviewerName: string, 
    reason: string,
    notes?: string
  ): Promise<{ success: boolean; updatedCase: ViolationCase; isDemo: boolean }> {
    const res = await apiClient.post<any>(`/violations/${encodeURIComponent(caseId)}/reject`, {
      reviewerName,
      reason,
      notes: notes || undefined
    });

    if (!res.success || !res.data) {
      throw new Error(res.error || `Failed to reject case ${caseId}`);
    }

    // Fetch fresh full case document from database to preserve all evidence, crops, and metadata
    const freshCase = await this.getCaseById(caseId);

    return {
      success: true,
      updatedCase: freshCase || mapBackendViolationToCase(res.data),
      isDemo: false
    };
  }

  async addCapturedCase(newCase: ViolationCase): Promise<ViolationCase> {
    const res = await apiClient.post<any>('/violations', {
      cameraId: newCase.camera.id,
      violationType: newCase.violationType,
      confidence: newCase.confidence,
      status: newCase.status,
      evidence: {
        imageUrl: newCase.evidenceImageUrl,
        thumbnailUrl: newCase.evidenceImageUrl,
        mimeType: 'image/jpeg'
      },
      evidenceQuality: newCase.evidenceQuality,
      boundingBoxes: newCase.boundingBoxes
    });

    if (res.success && res.data) {
      return mapBackendViolationToCase(res.data);
    }
    return newCase;
  }
}

export const violationsService = new ViolationsService();
