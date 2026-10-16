import type { ViolationCase, ViolationStatus, ViolationType, ReviewAuditLog } from '../types';
import { INITIAL_CASES } from '../data/mockData';
import { apiClient } from './api';

export interface ViolationFilters {
  status?: ViolationStatus | 'ALL';
  violationType?: ViolationType | 'ALL';
  searchQuery?: string;
  dateFrom?: string;
  dateTo?: string;
}

class ViolationsService {
  private localCases: ViolationCase[] = [...INITIAL_CASES];

  async getCases(filters?: ViolationFilters): Promise<{ cases: ViolationCase[]; isDemo: boolean }> {
    const res = await apiClient.get<ViolationCase[]>('/violations', this.localCases);
    let cases = res.isDemoData ? [...this.localCases] : res.data;

    if (filters) {
      if (filters.status && filters.status !== 'ALL') {
        cases = cases.filter(c => c.status === filters.status);
      }
      if (filters.violationType && filters.violationType !== 'ALL') {
        cases = cases.filter(c => c.violationType === filters.violationType);
      }
      if (filters.searchQuery && filters.searchQuery.trim() !== '') {
        const query = filters.searchQuery.toLowerCase().trim();
        cases = cases.filter(c => 
          c.id.toLowerCase().includes(query) ||
          c.camera.name.toLowerCase().includes(query) ||
          c.camera.location.toLowerCase().includes(query) ||
          c.linkedPerson?.fullName.toLowerCase().includes(query) ||
          c.linkedPerson?.vehiclePlate.toLowerCase().includes(query) ||
          c.linkedPerson?.personId.toLowerCase().includes(query)
        );
      }
    }

    return {
      cases,
      isDemo: res.isDemoData
    };
  }

  async getCaseById(caseId: string): Promise<ViolationCase | null> {
    const found = this.localCases.find(c => c.id === caseId);
    if (!found) return null;
    return found;
  }

  async approveDraft(
    caseId: string, 
    reviewerName: string, 
    notes?: string
  ): Promise<{ success: boolean; updatedCase: ViolationCase; isDemo: boolean }> {
    const existingIndex = this.localCases.findIndex(c => c.id === caseId);
    if (existingIndex === -1) {
      throw new Error(`Case ${caseId} not found`);
    }

    const current = this.localCases[existingIndex];
    const draftNumber = current.challanDraftNumber || `DFT-2026-${Math.floor(10000 + Math.random() * 90000)}`;

    const newAudit: ReviewAuditLog = {
      id: `audit-${Date.now()}`,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      actor: reviewerName,
      role: 'reviewer',
      action: 'DRAFT_APPROVED',
      notes: notes || 'Draft created for formal notice review under Section 129 Motor Vehicles Act.'
    };

    const updated: ViolationCase = {
      ...current,
      status: 'DRAFT_CREATED',
      challanDraftNumber: draftNumber,
      draftAmountInr: current.draftAmountInr || 1000,
      reviewerNotes: notes || current.reviewerNotes,
      reviewHistory: [newAudit, ...current.reviewHistory]
    };

    this.localCases[existingIndex] = updated;

    const res = await apiClient.post<ViolationCase>(`/violations/${caseId}/approve-draft`, {
      reviewerName,
      notes,
      challanDraftNumber: draftNumber
    }, updated);

    return {
      success: true,
      updatedCase: res.data,
      isDemo: res.isDemoData
    };
  }

  async rejectCase(
    caseId: string, 
    reviewerName: string, 
    reason: string,
    notes?: string
  ): Promise<{ success: boolean; updatedCase: ViolationCase; isDemo: boolean }> {
    const existingIndex = this.localCases.findIndex(c => c.id === caseId);
    if (existingIndex === -1) {
      throw new Error(`Case ${caseId} not found`);
    }

    const current = this.localCases[existingIndex];
    const newAudit: ReviewAuditLog = {
      id: `audit-${Date.now()}`,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      actor: reviewerName,
      role: 'reviewer',
      action: 'CASE_REJECTED',
      reason,
      notes: notes || `Case rejected: ${reason}`
    };

    const updated: ViolationCase = {
      ...current,
      status: 'REJECTED',
      rejectionReason: reason,
      reviewerNotes: notes || current.reviewerNotes,
      reviewHistory: [newAudit, ...current.reviewHistory]
    };

    this.localCases[existingIndex] = updated;

    const res = await apiClient.post<ViolationCase>(`/violations/${caseId}/reject`, {
      reviewerName,
      reason,
      notes
    }, updated);

    return {
      success: true,
      updatedCase: res.data,
      isDemo: res.isDemoData
    };
  }

  async addCapturedCase(newCase: ViolationCase): Promise<ViolationCase> {
    this.localCases.unshift(newCase);
    await apiClient.post<ViolationCase>('/violations', newCase, newCase);
    return newCase;
  }
}

export const violationsService = new ViolationsService();
