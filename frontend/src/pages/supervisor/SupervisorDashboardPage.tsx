import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Video, 
  ShieldAlert, 
  TrendingUp, 
  FileCheck2, 
  Activity, 
  Download, 
  Search 
} from 'lucide-react';
import { useApp } from '../../context';
import { StatCard } from '../../components/common/StatCard';
import { HourlyDistributionChart, MonthlyTrendChart } from '../../components/common/SimpleChart';
import { EmptyState } from '../../components/common/EmptyState';
import { statsService, EMPTY_DASHBOARD_STATS } from '../../services/statsService';
import type { DashboardStats } from '../../types';

export const SupervisorDashboardPage: React.FC = () => {
  const { 
    cases, 
    cameraSources, 
    officerActivities, 
    systemAuditLogs,
    activeNavTab,
    setActiveNavTab,
    addToast
  } = useApp();

  const [auditSearch, setAuditSearch] = useState('');
  const [auditCategoryFilter, setAuditCategoryFilter] = useState<string>('ALL');
  const [dateRange, setDateRange] = useState<'today' | 'monthly'>('today');
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>(EMPTY_DASHBOARD_STATS);

  useEffect(() => {
    let isMounted = true;
    statsService.getDashboardStats().then(res => {
      if (isMounted && res.success) {
        setDashboardStats(res.stats);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  // Derived stats for supervisory analysis
  const pendingCount = cases.filter(c => c.status === 'PENDING_REVIEW').length;
  const draftCount = cases.filter(c => c.status === 'DRAFT_CREATED').length;
  const rejectedCount = cases.filter(c => c.status === 'REJECTED').length;
  const totalEvaluated = draftCount + rejectedCount;
  const approvalRatio = totalEvaluated > 0 ? ((draftCount / totalEvaluated) * 100).toFixed(1) : '0.0';
  const falsePositiveRate = totalEvaluated > 0 ? ((rejectedCount / totalEvaluated) * 100).toFixed(1) : '0.0';
  const safePassages = Math.max(0, dashboardStats.todayTotalDetections - dashboardStats.todayNoHelmetCandidates);

  const filteredAuditLogs = systemAuditLogs.filter(log => {
    const matchesCategory = auditCategoryFilter === 'ALL' || log.eventCategory === auditCategoryFilter;
    const matchesSearch = 
      auditSearch.trim() === '' ||
      log.actor.toLowerCase().includes(auditSearch.toLowerCase()) ||
      log.description.toLowerCase().includes(auditSearch.toLowerCase()) ||
      log.id.toLowerCase().includes(auditSearch.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleExportSupervisoryReport = () => {
    addToast({
      type: 'success',
      title: 'Enforcement Report Generated',
      message: 'Official Supervisory Compliance Digest compiled for Bangalore City Traffic Directorate.'
    });
  };

  return (
    <div className="space-y-6">
      {/* Sub-navigation tabs for Supervisor */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {[
            { id: 'supervisor-analytics', label: 'Executive Analytics & KPIs' },
            { id: 'officer-activity', label: 'Officer Review Productivity' },
            { id: 'camera-performance', label: 'Camera Network Performance' },
            { id: 'supervisory-audit', label: 'System & Policy Audit Trail' }
          ].map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveNavTab(tab.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
                activeNavTab === tab.id 
                  ? 'bg-[#17324D] text-white shadow-xs' 
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={handleExportSupervisoryReport}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-xs"
        >
          <Download className="w-3.5 h-3.5 text-slate-600" />
          <span>Export Supervisory Digest</span>
        </button>
      </div>

      {/* 1. EXECUTIVE ANALYTICS & KPIS TAB */}
      {(activeNavTab === 'supervisor-analytics' || !activeNavTab) && (
        <div className="space-y-6">
          {/* Executive Overview Header */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-4 shadow-xs">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                  SUPERVISORY INTELLIGENCE
                </span>
                <span className="text-xs text-slate-400">•</span>
                <span className="text-xs text-slate-500">Live Traffic Enforcement Directorate</span>
              </div>
              <h2 className="text-lg font-bold text-slate-900 mt-1">
                Bangalore Urban Traffic Compliance &amp; Sanction Oversight
              </h2>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex rounded-lg border border-slate-200 p-0.5 bg-slate-100 text-xs">
                <button
                  type="button"
                  onClick={() => setDateRange('today')}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    dateRange === 'today' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Live Today
                </button>
                <button
                  type="button"
                  onClick={() => setDateRange('monthly')}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    dateRange === 'monthly' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Historical Summary
                </button>
              </div>
            </div>
          </div>

          {/* Senior Management KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="City Helmet Compliance Rate"
              value={`${(dashboardStats.complianceRatePercent ?? 100).toFixed(1)}%`}
              icon={<TrendingUp className="w-4 h-4" />}
              subtext={dashboardStats.todayTotalDetections > 0 ? `${safePassages} compliant riders of ${dashboardStats.todayTotalDetections} scans` : "No scans recorded today"}
              accentColor="#15803D"
              isDemo={false}
            />
            <StatCard
              label="Officer Sanction Integrity"
              value={`${approvalRatio}%`}
              icon={<FileCheck2 className="w-4 h-4" />}
              subtext="Draft validation rate by review officers"
              accentColor="#2563EB"
              isDemo={false}
            />
            <StatCard
              label="Estimated Challan Draft Value"
              value={`₹${(draftCount * 1000).toLocaleString()}`}
              icon={<Activity className="w-4 h-4" />}
              subtext="Provisional draft notices in process"
              accentColor="#F59E0B"
              isDemo={false}
            />
            <StatCard
              label="False Positive Suppression"
              value={`${falsePositiveRate}%`}
              icon={<ShieldAlert className="w-4 h-4" />}
              subtext={`${rejectedCount} shadow/occlusion rejections logged`}
              accentColor="#DC2626"
              isDemo={false}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HourlyDistributionChart
              data={dashboardStats.hourlyTrends}
              title="Surveillance Yield by Time Interval"
              isDemo={false}
            />
            <MonthlyTrendChart
              data={dashboardStats.monthlyTrends}
              title="Longitudinal Enforcement Volume & Sanctions"
              isDemo={false}
            />
          </div>

          {/* Outcome Distribution Summary Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-3">
              Candidate Case Disposition Breakdown (Current Shift)
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div className="p-3 rounded-lg bg-amber-50/70 border border-amber-200">
                <span className="text-amber-800 font-semibold block text-[11px]">Pending Officer Review</span>
                <span className="text-xl font-bold text-amber-900 mt-1 block">{pendingCount} cases</span>
                <span className="text-[11px] text-amber-700 mt-0.5 block">Waiting in triage queue</span>
              </div>
              <div className="p-3 rounded-lg bg-blue-50/70 border border-blue-200">
                <span className="text-blue-800 font-semibold block text-[11px]">Sanctioned Drafts</span>
                <span className="text-xl font-bold text-blue-900 mt-1 block">{draftCount} cases</span>
                <span className="text-[11px] text-blue-700 mt-0.5 block">Forwarded to notice unit</span>
              </div>
              <div className="p-3 rounded-lg bg-red-50/70 border border-red-200">
                <span className="text-red-800 font-semibold block text-[11px]">Officer Rejections</span>
                <span className="text-xl font-bold text-red-900 mt-1 block">{rejectedCount} cases</span>
                <span className="text-[11px] text-red-700 mt-0.5 block">False shadow/glare discard</span>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200">
                <span className="text-emerald-800 font-semibold block text-[11px]">Verified Safe Passages</span>
                <span className="text-xl font-bold text-emerald-900 mt-1 block">{safePassages} vehicles</span>
                <span className="text-[11px] text-emerald-700 mt-0.5 block">Automatic pass-through</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. OFFICER REVIEW PRODUCTIVITY TAB */}
      {activeNavTab === 'officer-activity' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <Users className="w-4 h-4 text-blue-600" />
                Reviewing Officer Activity &amp; Throughput Metrics
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Live evaluation metrics for traffic adjudication officers on duty during today's shift.
              </p>
            </div>
            <span className="text-xs text-slate-500">
              Active Shift Personnel: <strong>{officerActivities.length} Officers</strong>
            </span>
          </div>

          {officerActivities.length === 0 ? (
            <div className="p-8 text-center">
              <EmptyState
                title="No Officer Shifts Recorded"
                description="No officer duty logs recorded for today's shift in database."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Officer Name &amp; ID</th>
                    <th className="py-3 px-4">Rank / Designation</th>
                    <th className="py-3 px-4">Duty Shift</th>
                    <th className="py-3 px-4">Cases Evaluated</th>
                    <th className="py-3 px-4">Approved Drafts</th>
                    <th className="py-3 px-4">Rejections</th>
                    <th className="py-3 px-4">Avg Review Time</th>
                    <th className="py-3 px-4">Current Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {officerActivities.map(o => (
                    <tr key={o.officerId} className="hover:bg-slate-50/80">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900">{o.officerName}</div>
                        <div className="font-mono text-[11px] text-slate-400">{o.officerId}</div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-700">{o.rank}</td>
                      <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap">{o.shift}</td>
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-900">{o.totalReviewedToday}</td>
                      <td className="py-3.5 px-4 font-mono text-emerald-700 font-semibold">{o.approvedDrafts}</td>
                      <td className="py-3.5 px-4 font-mono text-red-600">{o.rejectedCount}</td>
                      <td className="py-3.5 px-4 font-mono text-slate-800">{o.avgReviewDurationSec}s / case</td>
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full border ${
                          o.status === 'ON_DUTY' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${o.status === 'ON_DUTY' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                          {o.status.replace('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 3. CAMERA NETWORK PERFORMANCE TAB */}
      {activeNavTab === 'camera-performance' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <Video className="w-4 h-4 text-blue-600" />
                Network Surveillance Feed Performance &amp; Optical Health
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Health telemetry, frame integrity, and candidate generation rate across all city surveillance nodes.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-emerald-700 font-semibold bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-md">
                {cameraSources.filter(c => c.status === 'ONLINE').length}/{cameraSources.length} Feeds Online
              </span>
            </div>
          </div>

          {cameraSources.length === 0 ? (
            <div className="p-8 text-center bg-white rounded-xl border border-slate-200">
              <EmptyState
                title="No Camera Feeds Configured"
                description="No surveillance camera streams are currently configured in database."
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cameraSources.map(cam => (
                <div key={cam.id} className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <span className="font-mono text-xs font-bold text-slate-800">{cam.id}</span>
                        <h4 className="text-sm font-bold text-slate-900">{cam.name}</h4>
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        cam.status === 'ONLINE' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        cam.status === 'STANDBY' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                        cam.status === 'DEGRADED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        'bg-red-50 text-red-700 border-red-200'
                      }`}>
                        {cam.status}
                      </span>
                    </div>

                    <div className="text-xs text-slate-500 mb-3">{cam.junction}</div>

                    <div className="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-200/60 text-xs text-center">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Today Scans:</span>
                        <span className="font-mono font-bold text-slate-900">{cam.dailyDetectionsCount}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Resolution:</span>
                        <span className="font-mono font-medium text-slate-800">{cam.resolution}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Target FPS:</span>
                        <span className="font-mono font-medium text-slate-800">{cam.fps} FPS</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                    <span>Stream Protocol: {cam.streamType}</span>
                    <span>Heartbeat: {cam.lastHeartbeat}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 4. SYSTEM & POLICY AUDIT TRAIL TAB */}
      {activeNavTab === 'supervisory-audit' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3 flex-1 max-w-xl">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={auditSearch}
                  onChange={e => setAuditSearch(e.target.value)}
                  placeholder="Search audit trail by actor, action description, or ID..."
                  className="w-full text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder-slate-400"
                />
              </div>

              <select
                value={auditCategoryFilter}
                onChange={e => setAuditCategoryFilter(e.target.value)}
                className="text-xs px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800"
              >
                <option value="ALL">All Categories</option>
                <option value="DRAFT_SANCTION">Draft Sanctions</option>
                <option value="SYSTEM_SETTING">Policy Updates</option>
                <option value="CAMERA_CONFIG">Camera Configs</option>
                <option value="POLICY_UPDATE">Supervisory Reports</option>
              </select>
            </div>

            <div className="text-xs text-slate-500">
              Showing <strong>{filteredAuditLogs.length}</strong> immutable audit entries
            </div>
          </div>

          {filteredAuditLogs.length === 0 ? (
            <div className="p-8 text-center">
              <EmptyState
                title="No Audit Records Found"
                description="Database contains no audit log entries matching your search filter."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Audit ID</th>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Actor / Officer</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Event Description</th>
                    <th className="py-3 px-4 text-right">IP Origin</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {filteredAuditLogs.map(log => (
                    <tr key={log.id} className="hover:bg-slate-50/80">
                      <td className="py-3 px-4 font-mono font-semibold text-slate-900">{log.id}</td>
                      <td className="py-3 px-4 text-slate-500 whitespace-nowrap">{log.timestamp}</td>
                      <td className="py-3 px-4 font-medium text-slate-800">{log.actor}</td>
                      <td className="py-3 px-4">
                        <span className="capitalize text-slate-600 font-semibold">{log.actorRole}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                          {log.eventCategory.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-700 max-w-md">{log.description}</td>
                      <td className="py-3 px-4 font-mono text-slate-400 text-right">{log.ipAddress}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
