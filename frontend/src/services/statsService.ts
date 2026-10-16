import type { DashboardStats } from '../types';
import { INITIAL_DASHBOARD_STATS } from '../data/mockData';
import { apiClient } from './api';

class StatsService {
  async getDashboardStats(): Promise<{ stats: DashboardStats; isDemo: boolean }> {
    const res = await apiClient.get<DashboardStats>('/stats/dashboard', INITIAL_DASHBOARD_STATS);
    return {
      stats: res.data,
      isDemo: res.isDemoData
    };
  }

  async getMonthlyStats(monthKey?: string) {
    const res = await apiClient.get('/stats/monthly', INITIAL_DASHBOARD_STATS.monthlyTrends);
    let trends = res.data;
    if (monthKey) {
      trends = trends.filter((m: { month: string }) => m.month.toLowerCase().includes(monthKey.toLowerCase()));
    }
    return {
      data: trends,
      isDemo: res.isDemoData
    };
  }

  async getDailyStats(dateRange?: { start?: string; end?: string }) {
    const res = await apiClient.get('/stats/daily', INITIAL_DASHBOARD_STATS.dailyHistory);
    let history = res.data;
    if (dateRange?.start && dateRange?.end) {
      history = history.filter((d: { date: string }) => d.date >= dateRange.start! && d.date <= dateRange.end!);
    }
    return {
      data: history,
      isDemo: res.isDemoData
    };
  }
}

export const statsService = new StatsService();
