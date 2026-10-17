import type { SystemSettings, SystemAuditLogEntry } from '../types';
import { apiClient } from './api';

export const DEFAULT_FRONTEND_SETTINGS: SystemSettings = {
  minConfidenceThreshold: 0.55,
  autoFlagPillionWithoutHelmet: true,
  autoFlagTripleRiding: true,
  requireSecondaryReviewForNightDetections: true,
  dataRetentionDays: 90,
  defaultDraftPenaltyInr: 1000
};

export function mapBackendAuditLog(doc: any): SystemAuditLogEntry {
  const ts = doc.timestamp 
    ? new Date(doc.timestamp).toISOString().replace('T', ' ').substring(0, 19)
    : new Date().toISOString().replace('T', ' ').substring(0, 19);

  let category: SystemAuditLogEntry['eventCategory'] = 'SYSTEM_SETTING';
  const action = String(doc.action || '');
  if (action.includes('CAMERA')) {
    category = 'CAMERA_CONFIG';
  } else if (action.includes('DRAFT') || action.includes('SANCTION') || action.includes('VIOLATION')) {
    category = 'DRAFT_SANCTION';
  } else if (action.includes('ROLE') || action.includes('USER')) {
    category = 'ROLE_CHANGE';
  } else if (action.includes('REPORT') || action.includes('SUPERVISOR')) {
    category = 'POLICY_UPDATE';
  }

  return {
    id: doc.id || (doc._id ? String(doc._id) : `AUDIT-${Date.now()}`),
    timestamp: ts,
    actor: doc.actorNameSnapshot || doc.actor || 'System Officer',
    actorRole: (doc.actorRoleSnapshot || doc.actorRole || 'admin') as any,
    eventCategory: category,
    description: doc.notes || doc.description || `${doc.action || 'Event'} on ${doc.entityType || 'system'}`,
    ipAddress: doc.metadata?.ip || '10.200.4.15'
  };
}

class SettingsService {
  async getSettings(): Promise<{ settings: SystemSettings; success: boolean; error?: string }> {
    const res = await apiClient.get<any>('/settings');
    if (!res.success || !res.data) {
      return { settings: DEFAULT_FRONTEND_SETTINGS, success: false, error: res.error };
    }
    const d = res.data;
    return {
      success: true,
      settings: {
        minConfidenceThreshold: d.minConfidenceThreshold ?? 0.55,
        autoFlagPillionWithoutHelmet: d.autoFlagPillionWithoutHelmet ?? true,
        autoFlagTripleRiding: d.autoFlagTripleRiding ?? true,
        requireSecondaryReviewForNightDetections: d.requireSecondaryReviewForNightDetections ?? true,
        dataRetentionDays: d.dataRetentionDays ?? 90,
        defaultDraftPenaltyInr: d.defaultDraftPenaltyInr ?? 1000
      }
    };
  }

  async updateSettings(payload: Partial<SystemSettings>): Promise<{ success: boolean; error?: string }> {
    const res = await apiClient.patch<any>('/settings', payload);
    return {
      success: res.success,
      error: res.error
    };
  }

  async getAuditLogs(params?: {
    entityType?: string;
    action?: string;
    page?: number;
    pageSize?: number;
  }): Promise<{ logs: SystemAuditLogEntry[]; total: number; success: boolean; error?: string }> {
    const query = new URLSearchParams();
    if (params?.entityType) query.append('entityType', params.entityType);
    if (params?.action) query.append('action', params.action);
    if (params?.page) query.append('page', params.page.toString());
    if (params?.pageSize) query.append('page_size', params.pageSize.toString());

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await apiClient.get<any>(`/audit-logs${qs}`);

    if (!res.success || !res.data) {
      return { logs: [], total: 0, success: false, error: res.error };
    }

    const items = Array.isArray(res.data) ? res.data : (Array.isArray((res.data as any).items) ? (res.data as any).items : []);
    const total = (res as any).total ?? items.length;

    return {
      logs: items.map(mapBackendAuditLog),
      total,
      success: true
    };
  }
}

export const settingsService = new SettingsService();
