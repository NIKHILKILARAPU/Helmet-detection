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

  const boundingBoxes: BoundingBox[] = Array.isArray(doc.boundingBoxes) ? doc.boundingBoxes.map((b: any, idx: number) => ({
    id: b.id || `bb-${idx}`,
    label: b.label || 'RIDER',
    confidence: b.confidence ?? 0.9,
    x: b.x ?? 0,
    y: b.y ?? 0,
    width: b.width ?? 0,
    height: b.height ?? 0,
    color: b.color || (b.label === 'Without Helmet' || b.label === 'NO_HELMET' ? '#DC2626' : '#15803D')
  })) : [];

  const reviewHistory: ReviewAuditLog[] = Array.isArray(doc.reviewHistory) && doc.reviewHistory.length > 0 
    ? doc.reviewHistory 
    : (doc.reviewedBy ? [{
        id: `audit-${doc.reviewedAt || Date.now()}`,
        timestamp: doc.reviewedAt ? new Date(doc.reviewedAt).toISOString().replace('T', ' ').substring(0, 19) : capturedAt,
        actor: String(doc.reviewedBy),
        role: 'reviewer',
        action: (doc.status === 'REJECTED' ? 'CASE_REJECTED' : 'DRAFT_APPROVED') as any,
        notes: doc.reviewerNotes
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
    plateMatch: doc.plateMatch
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

    return {
      success: true,
      updatedCase: mapBackendViolationToCase(res.data),
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

    return {
      success: true,
      updatedCase: mapBackendViolationToCase(res.data),
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
