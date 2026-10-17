import type { OfficerActivity, UserAccount } from '../types';
import { apiClient } from './api';

export function mapBackendShiftToActivity(doc: any): OfficerActivity {
  return {
    officerId: doc.officerId || (doc._id ? String(doc._id) : 'EMP-01'),
    officerName: doc.officerName || 'Duty Officer',
    rank: doc.officerRole === 'supervisor' ? 'Supervisory Inspector' : 'Traffic Enforcement Officer',
    shift: doc.shift || 'General Shift (08:00 - 16:00)',
    totalReviewedToday: doc.totalReviewedToday ?? 0,
    approvedDrafts: doc.approvedDrafts ?? 0,
    rejectedCount: doc.rejectedCount ?? 0,
    avgReviewDurationSec: doc.avgReviewDurationSec ?? 0,
    status: (doc.status as any) || 'ON_DUTY'
  };
}

export function mapBackendUserToAccount(doc: any): UserAccount {
  return {
    id: doc.id || doc.employeeId || 'USR-01',
    name: doc.name || 'Staff User',
    email: doc.email || '',
    role: (doc.role as any) || 'reviewer',
    department: doc.department || 'Traffic Enforcement Cell',
    status: (doc.status as any) || 'ACTIVE',
    lastLogin: doc.lastLoginAt ? new Date(doc.lastLoginAt).toLocaleString() : 'Active session'
  };
}

class OperationsService {
  async getOfficerShifts(): Promise<{ shifts: OfficerActivity[]; success: boolean; error?: string }> {
    const res = await apiClient.get<any[]>('/operations/shifts');
    if (!res.success || !res.data) {
      return { shifts: [], success: false, error: res.error };
    }
    const rawList = Array.isArray(res.data) ? res.data : [];
    return {
      shifts: rawList.map(mapBackendShiftToActivity),
      success: true
    };
  }

  async getStaffUsers(): Promise<{ users: UserAccount[]; success: boolean; error?: string }> {
    const res = await apiClient.get<any[]>('/auth/users');
    if (!res.success || !res.data) {
      return { users: [], success: false, error: res.error };
    }
    const rawList = Array.isArray(res.data) ? res.data : [];
    return {
      users: rawList.map(mapBackendUserToAccount),
      success: true
    };
  }
}

export const operationsService = new OperationsService();
