import type { DashboardStats, HourlyStat, DailyStat } from '../types';
import { apiClient } from './api';

export interface DashboardStatsResult {
  success: boolean;
  stats: DashboardStats;
  error?: string;
}

export const EMPTY_DASHBOARD_STATS: DashboardStats = {
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

class StatsService {
  async getDashboardStats(): Promise<DashboardStatsResult> {
    const [dashRes, hourlyRes] = await Promise.all([
      apiClient.get<any>('/stats/dashboard'),
      apiClient.get<any[]>('/stats/hourly')
    ]);

    if (!dashRes.success) {
      return {
        success: false,
        stats: EMPTY_DASHBOARD_STATS,
        error: dashRes.error || 'Failed to fetch dashboard statistics from server.'
      };
    }

    const d = dashRes.data || {};
    const hourlyRaw = (hourlyRes.success && Array.isArray(hourlyRes.data)) ? hourlyRes.data : [];

    const hourlyTrends: HourlyStat[] = hourlyRaw.map((h: any) => ({
      hour: h.hour || '00:00',
      detections: h.totalScanned || 0,
      violations: h.violationsDetected || 0
    }));

    const stats: DashboardStats = {
      todayTotalDetections: d.todayTotalDetections ?? 0,
      todayNoHelmetCandidates: d.todayNoHelmetCandidates ?? 0,
      todayPendingReview: d.todayPendingReview ?? 0,
      todayApprovedDrafts: d.todayApprovedDrafts ?? 0,
      todayRejectedCases: d.todayRejectedCases ?? 0,
      complianceRatePercent: d.complianceRatePercent ?? 100.0,
      hourlyTrends,
      monthlyTrends: [],
      dailyHistory: []
    };

    return {
      success: true,
      stats
    };
  }

  async getHourlyStats(): Promise<{ success: boolean; data: HourlyStat[]; error?: string }> {
    const res = await apiClient.get<any[]>('/stats/hourly');
    if (!res.success) {
      return { success: false, data: [], error: res.error };
    }
    const raw = Array.isArray(res.data) ? res.data : [];
    const data: HourlyStat[] = raw.map((h: any) => ({
      hour: h.hour || '00:00',
      detections: h.totalScanned || 0,
      violations: h.violationsDetected || 0
    }));
    return { success: true, data };
  }

  async getDailyStats(): Promise<{ success: boolean; data: DailyStat[]; error?: string }> {
    const res = await apiClient.get<any[]>('/stats/daily');
    if (!res.success) {
      return { success: false, data: [], error: res.error };
    }
    const raw = Array.isArray(res.data) ? res.data : [];
    const data: DailyStat[] = raw.map((d: any) => ({
      date: d._id || d.date || '',
      detections: d.scans || d.detections || 0,
      noHelmetCandidates: d.violations || 0,
      pendingReview: 0,
      approvedDrafts: 0,
      rejectedCases: 0
    }));
    return { success: true, data };
  }
}

export const statsService = new StatsService();
