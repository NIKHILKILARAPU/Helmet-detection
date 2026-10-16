import React, { useState, useMemo } from 'react';
import { 
  Camera, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  Search, 
  Eye, 
  Calendar, 
  Activity, 
  Database, 
  Cpu, 
  RefreshCw,
  UserPlus
} from 'lucide-react';
import { useApp } from '../../context';
import { StatCard } from '../common/StatCard';
import { StatusBadge } from '../common/StatusBadge';
import { HourlyDistributionChart, MonthlyTrendChart } from '../common/SimpleChart';
import { Modal } from '../common/Modal';
import { EvidenceViewer } from '../common/EvidenceViewer';
import type { ViolationCase, RegisteredPerson } from '../../types';
import { INITIAL_DASHBOARD_STATS } from '../../data/mockData';

export const AdminDashboard: React.FC = () => {
  const { 
    cases, 
    persons, 
    userAccounts, 
    systemHealth, 
    refreshHealth, 
    activeNavTab,
    setActiveNavTab
  } = useApp();

  const [dateFilterMode, setDateFilterMode] = useState<'today' | 'monthly'>('today');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedCaseForModal, setSelectedCaseForModal] = useState<ViolationCase | null>(null);
  const [selectedPersonForModal, setSelectedPersonForModal] = useState<RegisteredPerson | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Filtered cases for table
  const filteredCases = useMemo(() => {
    return cases.filter(c => {
      const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
      const matchesSearch = 
        searchQuery.trim() === '' ||
        c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.camera.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.camera.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.linkedPerson?.fullName.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.linkedPerson?.vehiclePlate.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesStatus && matchesSearch;
    });
  }, [cases, statusFilter, searchQuery]);

  // Derived metrics from current cases state
  const pendingCount = cases.filter(c => c.status === 'PENDING_REVIEW').length;
  const draftCount = cases.filter(c => c.status === 'DRAFT_CREATED').length;
  const rejectedCount = cases.filter(c => c.status === 'REJECTED').length;

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await refreshHealth();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  return (
    <div className="space-y-6">
      {/* Sub-navigation tabs for Admin */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {[
            { id: 'overview', label: 'Enforcement Overview' },
            { id: 'violations', label: 'Recent Violations' },
            { id: 'persons', label: 'Registered Directory' },
            { id: 'users', label: 'User Roles & Access' },
            { id: 'health', label: 'System Health' }
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

        {/* Refresh & Mode status */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50"
            title="Refresh metrics and health"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-blue-600' : 'text-slate-500'}`} />
            <span>{isRefreshing ? 'Checking...' : 'Refresh Status'}</span>
          </button>
        </div>
      </div>

      {/* 1. OVERVIEW VIEW */}
      {(activeNavTab === 'overview' || !activeNavTab) && (
        <div className="space-y-6">
          {/* Top Filter and Date Range Control */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-4 shadow-xs">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-bold text-slate-800">Reporting Interval:</span>
              <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-100">
                <button
                  type="button"
                  onClick={() => setDateFilterMode('today')}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    dateFilterMode === 'today' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Today (16 Oct 2026)
                </button>
                <button
                  type="button"
                  onClick={() => setDateFilterMode('monthly')}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    dateFilterMode === 'monthly' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Monthly Summary (Oct 2026)
                </button>
              </div>
            </div>

            <div className="text-xs text-slate-500 flex items-center gap-2">
              <span>Jurisdiction: <strong>Bengaluru City Traffic Police (BCTP)</strong></span>
              <span className="text-slate-300">•</span>
              <span className="text-emerald-700 font-medium">4 Active Camera Feeds</span>
            </div>
          </div>

          {/* Key Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total Scanned Today"
              value={INITIAL_DASHBOARD_STATS.todayTotalDetections}
              icon={<Camera className="w-4 h-4" />}
              subtext="Across 4 surveillance junction cameras"
              accentColor="#2563EB"
              isDemo={true}
            />
            <StatCard
              label="Pending Review"
              value={pendingCount}
              icon={<AlertTriangle className="w-4 h-4" />}
              subtext="Awaiting human officer verification"
              accentColor="#F59E0B"
              isDemo={true}
            />
            <StatCard
              label="Approved Challan Drafts"
              value={draftCount + INITIAL_DASHBOARD_STATS.todayApprovedDrafts}
              icon={<CheckCircle2 className="w-4 h-4" />}
              subtext="Drafts generated (no fine triggered yet)"
              accentColor="#15803D"
              isDemo={true}
            />
            <StatCard
              label="Rejected / False Alerts"
              value={rejectedCount + INITIAL_DASHBOARD_STATS.todayRejectedCases}
              icon={<XCircle className="w-4 h-4" />}
              subtext="Occlusions, false shadows, safe riders"
              accentColor="#DC2626"
              isDemo={true}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HourlyDistributionChart 
              data={INITIAL_DASHBOARD_STATS.hourlyTrends}
              isDemo={true}
            />
            <MonthlyTrendChart 
              data={INITIAL_DASHBOARD_STATS.monthlyTrends}
              isDemo={true}
            />
          </div>

          {/* Quick Violations Preview */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50">
              <div>
                <h3 className="text-sm font-bold text-slate-800">Recent Candidate Detections</h3>
                <p className="text-xs text-slate-500">Live feed detections queued for verification</p>
              </div>
              <button
                type="button"
                onClick={() => setActiveNavTab('violations')}
                className="text-xs font-semibold text-blue-600 hover:text-blue-800"
              >
                View Complete Table ({cases.length}) &rarr;
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Case ID</th>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Camera / Location</th>
                    <th className="py-3 px-4">Violation Type</th>
                    <th className="py-3 px-4">Registered Owner</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {cases.slice(0, 4).map(c => (
                    <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                        {c.id}
                      </td>
                      <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                        {c.timestamp.split(' ')[1]}
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-800">{c.camera.name}</div>
                        <div className="text-[11px] text-slate-400">{c.camera.location}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-medium text-slate-800">
                          {c.violationType.replace(/_/g, ' ')}
                        </span>
                        <span className="ml-1 text-[11px] text-slate-400">
                          ({(c.confidence * 100).toFixed(0)}%)
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {c.linkedPerson ? (
                          <div>
                            <span className="font-medium text-slate-800">{c.linkedPerson.fullName}</span>
                            <span className="block text-[11px] text-slate-400 font-mono">
                              {c.linkedPerson.vehiclePlate}
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">Unmatched Candidate</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={c.status} size="sm" />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedCaseForModal(c)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-500" />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 2. RECENT VIOLATIONS TABLE TAB */}
      {activeNavTab === 'violations' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {/* Table Filters Bar */}
          <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5 flex-1 max-w-xl">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search by Case ID, Camera, Owner, or Vehicle Plate..."
                  className="w-full text-xs pl-9 pr-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <select
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}
                className="text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="PENDING_REVIEW">Pending Review</option>
                <option value="DRAFT_CREATED">Draft Created</option>
                <option value="REJECTED">Rejected</option>
                <option value="REVIEWED">Verified &amp; Reviewed</option>
              </select>
            </div>

            <div className="text-xs text-slate-500">
              Showing <strong>{filteredCases.length}</strong> of {cases.length} records
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Case ID</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Camera Feed</th>
                  <th className="py-3 px-4">Violation Predicted</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Registered Owner</th>
                  <th className="py-3 px-4">Masked Mobile</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredCases.map(c => (
                  <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                      {c.id}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">
                      {c.timestamp}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-slate-800">{c.camera.name}</div>
                      <div className="text-[11px] text-slate-400">{c.camera.location}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-semibold text-slate-800">
                        {c.violationType.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`font-semibold ${c.confidence >= 0.9 ? 'text-emerald-700' : 'text-amber-700'}`}>
                        {(c.confidence * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      {c.linkedPerson ? (
                        <div>
                          <div className="font-medium text-slate-900">{c.linkedPerson.fullName}</div>
                          <div className="text-[11px] font-mono text-slate-500">{c.linkedPerson.vehiclePlate}</div>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Unmatched</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600">
                      {c.linkedPerson?.maskedMobile || '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={c.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedCaseForModal(c)}
                        className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100"
                      >
                        <Eye className="w-3.5 h-3.5 text-blue-600" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. REGISTERED PERSON DIRECTORY TAB */}
      {activeNavTab === 'persons' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800">State Transport Vehicle &amp; Citizen Registry</h3>
              <p className="text-xs text-slate-500">
                Verified registration records. Face recognition is explicitly prohibited; matching requires authorized state plate registration.
              </p>
            </div>
            <div className="text-xs text-slate-500">
              Total pre-registered demo records: <strong>{persons.length}</strong>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {persons.map(person => (
              <div 
                key={person.personId} 
                className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:border-slate-300 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">{person.fullName}</h4>
                      <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                        <span className="font-mono">{person.personId}</span>
                        <span>•</span>
                        <span>{person.city}</span>
                      </div>
                    </div>
                    <StatusBadge status={person.identityStatus} size="sm" />
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[11px]">Masked Mobile:</span>
                      <span className="font-mono font-medium text-slate-800">{person.maskedMobile}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Linked Cases:</span>
                      <span className="font-semibold text-slate-800">{person.linkedCasesCount} cases</span>
                    </div>
                  </div>

                  <div className="mt-3">
                    <span className="text-slate-400 block text-[11px] mb-1">Registered Vehicles:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {person.linkedVehicles.map(v => (
                        <span 
                          key={v.plateNumber} 
                          className="px-2 py-0.5 rounded bg-slate-100 font-mono text-[11px] text-slate-800 font-semibold border border-slate-200"
                        >
                          {v.plateNumber} ({v.model.split('-')[0].trim()})
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">
                    Notifications: {person.notificationHistory.length} notices logged
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedPersonForModal(person)}
                    className="text-xs font-semibold text-blue-600 hover:text-blue-800"
                  >
                    View Full Profile &rarr;
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. USER & ROLE MANAGEMENT TAB */}
      {activeNavTab === 'users' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Authorized Personnel &amp; Role Management</h3>
              <p className="text-xs text-slate-500">Active role mappings across Admin, Reviewer, Operator, and Citizen interfaces</p>
            </div>
            <button
              type="button"
              onClick={() => alert('Role creation is disabled in demo mode.')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Add Staff User (Demo)</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">User ID</th>
                  <th className="py-3 px-4">Staff Name</th>
                  <th className="py-3 px-4">Department / Unit</th>
                  <th className="py-3 px-4">Assigned Role</th>
                  <th className="py-3 px-4">Account Status</th>
                  <th className="py-3 px-4">Last Activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {userAccounts.map(u => (
                  <tr key={u.id} className="hover:bg-slate-50/80">
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">{u.id}</td>
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900">{u.name}</div>
                      <div className="text-[11px] text-slate-400">{u.email}</div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">{u.department}</td>
                    <td className="py-3.5 px-4">
                      <span className="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold capitalize bg-slate-100 text-slate-800 border border-slate-200">
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-[11px]">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        {u.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap">{u.lastLogin}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. SYSTEM HEALTH TAB */}
      {activeNavTab === 'health' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-bold text-slate-800">Infrastructure &amp; Model Integration Status</h3>
                <p className="text-xs text-slate-500">Continuous telemetry across FastAPI backend, MongoDB, and YOLOv8 inference</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                  systemHealth.isBackendConnected ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                }`}>
                  {systemHealth.isBackendConnected ? 'Live Backend Connected' : 'Demo Mode Active'}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* API Service */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Activity className="w-4 h-4 text-blue-600" />
                    FastAPI REST Server
                  </span>
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    {systemHealth.api.status}
                  </span>
                </div>
                <div className="text-xs text-slate-600 mb-1">{systemHealth.api.message}</div>
                <div className="text-[11px] text-slate-400">Response Latency: {systemHealth.api.responseTimeMs}ms</div>
              </div>

              {/* Database */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-emerald-600" />
                    MongoDB Cluster
                  </span>
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    {systemHealth.database.status}
                  </span>
                </div>
                <div className="text-xs text-slate-600 mb-1">{systemHealth.database.message}</div>
                <div className="text-[11px] text-slate-400">Response Latency: {systemHealth.database.responseTimeMs}ms</div>
              </div>

              {/* AI Inference Model */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Cpu className="w-4 h-4 text-purple-600" />
                    YOLOv8 Helmet Engine
                  </span>
                  <span className="text-[11px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    {systemHealth.model.status}
                  </span>
                </div>
                <div className="text-xs text-slate-600 mb-1">{systemHealth.model.message}</div>
                <div className="text-[11px] text-slate-400">Boundary: Demo Simulation Active</div>
              </div>

              {/* Surveillance Cameras */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Camera className="w-4 h-4 text-blue-600" />
                    Camera Feeds
                  </span>
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    {systemHealth.camera.status}
                  </span>
                </div>
                <div className="text-xs text-slate-600 mb-1">{systemHealth.camera.message}</div>
                <div className="text-[11px] text-slate-400">Webcam API: navigator.mediaDevices Ready</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Case Details Inspection Modal */}
      {selectedCaseForModal && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedCaseForModal(null)}
          title={`Detection Inspection: ${selectedCaseForModal.id}`}
          subtitle={`Captured on ${selectedCaseForModal.timestamp} at ${selectedCaseForModal.camera.name}`}
          maxWidth="3xl"
        >
          <div className="space-y-4">
            <EvidenceViewer caseData={selectedCaseForModal} showDetails={true} />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
                <h4 className="font-bold text-slate-800 mb-2">Registration Association</h4>
                {selectedCaseForModal.linkedPerson ? (
                  <div className="space-y-1 text-slate-700">
                    <div>Owner: <strong>{selectedCaseForModal.linkedPerson.fullName}</strong></div>
                    <div>Person ID: <span className="font-mono">{selectedCaseForModal.linkedPerson.personId}</span></div>
                    <div>Vehicle Plate: <span className="font-mono font-semibold">{selectedCaseForModal.linkedPerson.vehiclePlate}</span></div>
                    <div>Model: {selectedCaseForModal.linkedPerson.vehicleModel}</div>
                    <div>Masked Phone: <span className="font-mono">{selectedCaseForModal.linkedPerson.maskedMobile}</span></div>
                  </div>
                ) : (
                  <div className="text-slate-400 italic">No registered owner linked yet.</div>
                )}
              </div>

              <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
                <h4 className="font-bold text-slate-800 mb-2">Review Status &amp; Draft Details</h4>
                <div className="space-y-1 text-slate-700">
                  <div className="flex items-center gap-2">
                    <span>Status:</span>
                    <StatusBadge status={selectedCaseForModal.status} size="sm" />
                  </div>
                  {selectedCaseForModal.challanDraftNumber && (
                    <div>Draft Number: <span className="font-mono font-semibold">{selectedCaseForModal.challanDraftNumber}</span></div>
                  )}
                  {selectedCaseForModal.draftAmountInr && (
                    <div>Proposed Fine Amount: <strong>₹{selectedCaseForModal.draftAmountInr}</strong></div>
                  )}
                  {selectedCaseForModal.reviewerNotes && (
                    <div className="mt-1 pt-1 border-t border-slate-200">
                      <span className="text-slate-500 block text-[11px]">Reviewer Remarks:</span>
                      <span className="text-slate-800 italic">"{selectedCaseForModal.reviewerNotes}"</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedCaseForModal(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Person Details Modal */}
      {selectedPersonForModal && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedPersonForModal(null)}
          title={`Registered Citizen: ${selectedPersonForModal.fullName}`}
          subtitle={`Internal ID: ${selectedPersonForModal.personId} • ${selectedPersonForModal.city}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div>
                <span className="text-slate-400 block text-[11px]">Masked Contact:</span>
                <span className="font-mono font-semibold text-slate-800">{selectedPersonForModal.maskedMobile}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Identity Status:</span>
                <StatusBadge status={selectedPersonForModal.identityStatus} size="sm" />
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Email Address:</span>
                <span className="text-slate-700">{selectedPersonForModal.email}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Linked Cases:</span>
                <span className="font-bold text-slate-900">{selectedPersonForModal.linkedCasesCount}</span>
              </div>
            </div>

            <div>
              <h4 className="font-bold text-slate-800 mb-2">Registered Vehicles (State Vahan Database)</h4>
              <div className="space-y-2">
                {selectedPersonForModal.linkedVehicles.map(v => (
                  <div key={v.plateNumber} className="p-2.5 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="font-mono font-bold text-slate-900">{v.plateNumber}</div>
                      <div className="text-[11px] text-slate-500">{v.model} ({v.vehicleType})</div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {v.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className="font-bold text-slate-800 mb-2">Notification &amp; Delivery Log</h4>
              {selectedPersonForModal.notificationHistory.length > 0 ? (
                <div className="space-y-2">
                  {selectedPersonForModal.notificationHistory.map(n => (
                    <div key={n.id} className="p-2.5 rounded-lg border border-slate-100 bg-slate-50">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800">{n.title}</span>
                        <span className="text-[10px] text-slate-400">{n.date}</span>
                      </div>
                      <p className="text-[11px] text-slate-600 mt-1">{n.preview}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-slate-400 italic p-3 text-center bg-slate-50 rounded-lg">
                  No notifications dispatched for this account.
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedPersonForModal(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close Profile
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
