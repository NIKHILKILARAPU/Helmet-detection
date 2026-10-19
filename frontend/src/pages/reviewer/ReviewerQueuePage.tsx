import React, { useState, useEffect } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Search, 
  FileCheck2, 
  User, 
  History, 
  Check,
  Users,
  Lock,
  AlertCircle,
  RefreshCw,
  Loader2,
  ImageIcon,
  ShieldAlert,
  Info,
  Bike
} from 'lucide-react';
import { useApp } from '../../context';
import type { ViolationStatus } from '../../types';
import { EvidenceViewer } from '../../components/common/EvidenceViewer';
import { StatusBadge } from '../../components/common/StatusBadge';
import { ConfirmationDialog } from '../../components/common/ConfirmationDialog';
import { EmptyState } from '../../components/common/EmptyState';
import { violationsService } from '../../services/violationsService';

export const ReviewerQueuePage: React.FC = () => {
  const { cases, approveDraft, rejectCase, refreshCases, isCasesLoading, casesError } = useApp();

  const [activeTab, setActiveTab] = useState<ViolationStatus | 'ALL'>('PENDING_REVIEW');
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [actionLoadingCaseId, setActionLoadingCaseId] = useState<string | null>(null);
  const [isReconciling, setIsReconciling] = useState(false);
  const [reconcileResult, setReconcileResult] = useState<string | null>(null);

  useEffect(() => {
    refreshCases();
  }, [refreshCases]);

  // Dialog state
  const [dialogState, setDialogState] = useState<{
    isOpen: boolean;
    type: 'APPROVE_DRAFT' | 'REJECT_CASE';
    caseId?: string;
  }>({
    isOpen: false,
    type: 'APPROVE_DRAFT'
  });

  // Filter cases: enforce that BICYCLE cases never leak into PENDING_REVIEW queue
  const filteredCases = cases.filter(c => {
    let matchesTab = false;
    if (activeTab === 'ALL') {
      matchesTab = true;
    } else if (activeTab === 'PENDING_REVIEW') {
      const isCyclist = c.riderDetails?.vehicleType === 'BICYCLE' || c.riderDetails?.exclusionReason === 'BICYCLE_EXCLUDED';
      matchesTab = c.status === 'PENDING_REVIEW' && !isCyclist;
    } else {
      matchesTab = c.status === activeTab;
    }

    const q = searchQuery.trim().toLowerCase();
    const plate = c.linkedPerson?.vehiclePlate || c.plateMatch?.normalizedPlate || '';
    const matchesSearch = 
      q === '' ||
      c.id.toLowerCase().includes(q) ||
      (c.camera?.name && c.camera.name.toLowerCase().includes(q)) ||
      plate.toLowerCase().includes(q);

    return matchesTab && matchesSearch;
  });

  const activeCase = (selectedCaseId ? cases.find(c => c.id === selectedCaseId) : null) || filteredCases[0] || null;

  const handleReconcileCyclists = async () => {
    setIsReconciling(true);
    setReconcileResult(null);
    try {
      const res = await violationsService.reconcileCyclists();
      setReconcileResult(`Reconciled ${res.reconciledCount} historical cyclist case(s) to REJECTED status.`);
      await refreshCases();
    } catch (err: any) {
      setReconcileResult(err?.message || 'Failed to reconcile cyclist records.');
    } finally {
      setIsReconciling(false);
    }
  };

  const handleOpenApproveDialog = () => {
    if (!activeCase || activeCase.status !== 'PENDING_REVIEW') return;
    setDialogState({
      isOpen: true,
      type: 'APPROVE_DRAFT',
      caseId: activeCase.id
    });
  };

  const handleOpenRejectDialog = () => {
    if (!activeCase || activeCase.status !== 'PENDING_REVIEW') return;
    setDialogState({
      isOpen: true,
      type: 'REJECT_CASE',
      caseId: activeCase.id
    });
  };

  const handleConfirmAction = async (notes?: string, reason?: string) => {
    if (!activeCase || actionLoadingCaseId) return;
    const targetCaseId = activeCase.id;
    setActionLoadingCaseId(targetCaseId);

    try {
      if (dialogState.type === 'APPROVE_DRAFT') {
        const ok = await approveDraft(targetCaseId, notes || reviewerNotes);
        if (ok) {
          setReviewerNotes('');
          setDialogState(prev => ({ ...prev, isOpen: false }));
        }
      } else if (dialogState.type === 'REJECT_CASE') {
        const ok = await rejectCase(targetCaseId, reason || 'FALSE_DETECTION_SHADOW', notes || reviewerNotes);
        if (ok) {
          setReviewerNotes('');
          setDialogState(prev => ({ ...prev, isOpen: false }));
        }
      }
    } finally {
      setActionLoadingCaseId(null);
    }
  };

  const siblingCases = (activeCase && activeCase.evidenceImageUrl)
    ? cases.filter(c => c.evidenceImageUrl === activeCase.evidenceImageUrl && c.id !== activeCase.id)
    : [];

  return (
    <div className="space-y-4">
      {/* Reviewer Header & Guidance Notice */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileCheck2 className="w-5 h-5 text-blue-600" />
              Candidate Evidence Review &amp; Draft Verification Desk
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Human-in-the-loop verification under Section 129 Motor Vehicles Act. Approval creates a provisional draft only.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-slate-700">Queue Metrics:</span>
            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold">
              {cases.filter(c => c.status === 'PENDING_REVIEW' && c.riderDetails?.vehicleType !== 'BICYCLE' && c.riderDetails?.exclusionReason !== 'BICYCLE_EXCLUDED').length} Pending
            </span>
            <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-bold">
              {cases.filter(c => c.status === 'DRAFT_CREATED').length} Drafts
            </span>

            <button
              type="button"
              onClick={() => refreshCases()}
              disabled={isCasesLoading}
              className="ml-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
              title="Refresh queue from server"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isCasesLoading ? 'animate-spin text-blue-600' : ''}`} />
              <span>Refresh</span>
            </button>

            <button
              type="button"
              onClick={handleReconcileCyclists}
              disabled={isReconciling || isCasesLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-300 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
              title="Audit and exclude historical bicycle records from active queue"
            >
              {isReconciling ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Bike className="w-3.5 h-3.5 text-amber-600" />
              )}
              <span>Reconcile Cyclists</span>
            </button>
          </div>
        </div>

        {casesError && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>Failed to fetch latest violation cases: {casesError}</span>
            </div>
            <button
              type="button"
              onClick={() => refreshCases()}
              className="px-2.5 py-1 bg-white border border-rose-300 rounded text-rose-800 font-semibold hover:bg-rose-100 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {reconcileResult && (
          <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{reconcileResult}</span>
            </div>
            <button
              type="button"
              onClick={() => setReconcileResult(null)}
              className="text-slate-400 hover:text-slate-600 font-bold"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Main Review Workspace Layout: Left Queue List, Right Inspection Deck */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Queue Items List (5 Cols) */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col h-[740px]">
          {/* Status Tabs */}
          <div className="p-3 border-b border-slate-200 bg-slate-50/50 space-y-2.5">
            <div className="flex rounded-lg border border-slate-200 p-0.5 bg-slate-100 text-xs font-medium">
              {[
                { id: 'PENDING_REVIEW', label: 'Pending' },
                { id: 'DRAFT_CREATED', label: 'Drafts' },
                { id: 'REJECTED', label: 'Rejected' },
                { id: 'ALL', label: 'All Cases' }
              ].map(tab => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex-1 py-1.5 rounded-md text-center transition-colors text-xs ${
                    activeTab === tab.id 
                      ? 'bg-white text-slate-900 font-bold shadow-xs' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search ID, camera, or plate..."
                className="w-full text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Queue List Items */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-1">
            {filteredCases.length === 0 ? (
              <div className="p-6 text-center">
                <EmptyState
                  title="No cases in this queue"
                  description="All candidate cases matching the current filter have been evaluated."
                />
              </div>
            ) : (
              filteredCases.map(item => {
                const isSelected = activeCase?.id === item.id;

                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedCaseId(item.id)}
                    className={`p-3.5 rounded-lg cursor-pointer transition-all ${
                      isSelected 
                        ? 'bg-blue-50/70 border border-blue-200' 
                        : 'hover:bg-slate-50 border border-transparent'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        {item.riderCropUrl ? (
                          <img
                            src={item.riderCropUrl}
                            alt={`Rider crop ${item.id}`}
                            className="w-10 h-10 rounded-md object-cover border border-rose-200 bg-slate-900 shrink-0"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0 text-slate-400">
                            <ImageIcon className="w-5 h-5" />
                          </div>
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-xs text-slate-900">{item.id}</span>
                            <StatusBadge status={item.status} size="sm" />
                          </div>
                          <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5">
                            <Clock className="w-3 h-3 text-slate-400" />
                            <span>{item.timestamp}</span>
                          </div>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <span className={`text-xs font-bold ${item.confidence >= 0.9 ? 'text-emerald-700' : 'text-amber-700'}`}>
                          {(item.confidence * 100).toFixed(0)}% Conf.
                        </span>
                        <div className="text-[10px] text-slate-400 font-medium">
                          {item.evidenceQuality} Quality
                        </div>
                      </div>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-xs text-slate-700 pt-2 border-t border-slate-100">
                      <span className="font-medium text-slate-800 truncate max-w-[180px]">
                        {item.violationType.replace(/_/g, ' ')}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {item.riderDetails?.vehicleType && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium border ${
                            item.riderDetails.vehicleType === 'MOTORCYCLE'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : item.riderDetails.vehicleType === 'BICYCLE'
                                ? 'bg-orange-50 text-orange-700 border-orange-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}>
                            {item.riderDetails.vehicleType}
                          </span>
                        )}
                        <span className="font-mono text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded text-[11px]">
                          {item.linkedPerson?.vehiclePlate || (item.plateMatch?.normalizedPlate ? item.plateMatch.normalizedPlate : 'Unmatched')}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Case Inspection Deck & Actions (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          {activeCase ? (
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 space-y-5">
              {/* Top Case ID & Quick Meta */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-200">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-base font-bold text-slate-900 font-mono">
                      {activeCase.id}
                    </h3>
                    <StatusBadge status={activeCase.status} size="md" />
                    {activeCase.riderDetails?.vehicleType && (
                      <span className={`text-xs px-2 py-0.5 rounded font-semibold border ${
                        activeCase.riderDetails.vehicleType === 'MOTORCYCLE'
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : activeCase.riderDetails.vehicleType === 'BICYCLE'
                            ? 'bg-orange-50 text-orange-700 border-orange-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}>
                        Vehicle: {activeCase.riderDetails.vehicleType}
                      </span>
                    )}
                    {activeCase.riderDetails?.exclusionReason && (
                      <span className="text-xs px-2 py-0.5 rounded font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                        {activeCase.riderDetails.exclusionReason.replace(/_/g, ' ')}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Recorded by {activeCase.camera.name} ({activeCase.camera.location})
                  </div>
                </div>

                <div className="text-right text-xs">
                  <span className="text-slate-400 block text-[11px]">Detection Timestamp:</span>
                  <span className="font-semibold text-slate-800">{activeCase.timestamp}</span>
                </div>
              </div>

              {/* Multi-Rider Single Frame Context Banner */}
              {siblingCases.length > 0 && (
                <div className="rounded-xl bg-indigo-50/80 border border-indigo-200 p-3.5 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-indigo-700" />
                      <span className="text-xs font-bold text-indigo-950">
                        Multi-Rider Frame Context ({siblingCases.length + 1} riders detected in same frame)
                      </span>
                    </div>
                    <span className="text-[11px] text-indigo-700 font-semibold bg-indigo-100 px-2 py-0.5 rounded">
                      Independent Review Mandated
                    </span>
                  </div>
                  <p className="text-xs text-indigo-900 leading-relaxed">
                    This capture contains multiple detected unhelmeted riders. Review decisions apply <strong>strictly to current rider {activeCase.id}</strong>. Sibling cases remain unaffected.
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[11px] font-semibold text-indigo-900 mr-1">Switch Rider:</span>
                    <span className="px-2 py-1 rounded-md text-xs font-mono font-bold bg-indigo-600 text-white shadow-xs">
                      Active: {activeCase.id}
                    </span>
                    {siblingCases.map(sib => (
                      <button
                        key={sib.id}
                        type="button"
                        onClick={() => setSelectedCaseId(sib.id)}
                        className="px-2 py-1 rounded-md text-xs font-mono font-semibold bg-white text-slate-700 hover:text-indigo-600 hover:border-indigo-300 border border-slate-200 transition-colors flex items-center gap-1.5 shadow-2xs cursor-pointer"
                      >
                        <span>{sib.id}</span>
                        <StatusBadge status={sib.status} size="sm" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Evidence Viewer Stage with Bounding Boxes */}
              <EvidenceViewer caseData={activeCase} showDetails={true} />

              {/* Rider Detection & Vehicle Diagnostics Panel */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-indigo-600" />
                    Rider Detection &amp; Vehicle Diagnostics
                  </h4>
                  <div className="flex items-center gap-1.5">
                    {activeCase.riderDetails?.eligibleForChallan !== false ? (
                      <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        Eligible for Challan
                      </span>
                    ) : (
                      <span className="text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                        Excluded from Challan
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Helmet Status:</span>
                    <span className="font-semibold text-slate-900">
                      {activeCase.riderDetails?.helmetClass || activeCase.violationType.replace(/_/g, ' ')}
                    </span>
                    {activeCase.riderDetails?.helmetConfidence !== undefined && (
                      <span className="text-[10px] text-slate-500 block">
                        {(activeCase.riderDetails.helmetConfidence * 100).toFixed(0)}% conf
                      </span>
                    )}
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Vehicle Classification:</span>
                    <span className={`font-semibold ${
                      activeCase.riderDetails?.vehicleType === 'BICYCLE' 
                        ? 'text-orange-700 font-bold' 
                        : activeCase.riderDetails?.vehicleType === 'UNCERTAIN'
                          ? 'text-amber-700'
                          : 'text-blue-700'
                    }`}>
                      {activeCase.riderDetails?.vehicleType || 'MOTORCYCLE'}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      Assoc Score: {activeCase.riderDetails?.associationScore !== undefined 
                        ? `${(activeCase.riderDetails.associationScore * 100).toFixed(0)}%` 
                        : '100%'}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Exclusion Policy:</span>
                    <span className="font-semibold text-slate-800">
                      {activeCase.riderDetails?.exclusionReason 
                        ? activeCase.riderDetails.exclusionReason.replace(/_/g, ' ') 
                        : 'None (Motorized)'}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Review Pipeline:</span>
                    <span className="font-semibold text-slate-800 font-mono text-[11px]">
                      {activeCase.riderDetails?.reviewStatus || activeCase.status}
                    </span>
                  </div>
                </div>

                {activeCase.riderDetails?.vehicleType === 'BICYCLE' && (
                  <div className="p-2.5 rounded-lg bg-orange-50 border border-orange-200 text-[11px] text-orange-900 flex items-start gap-2">
                    <Info className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
                    <span>
                      <strong>Statutory Bicycle Exemption:</strong> Section 129 Motor Vehicles Act applies only to motorized two-wheelers. Pedal cyclists are exempt from mandatory helmet challans. This candidate case cannot be approved as a motorized violation.
                    </span>
                  </div>
                )}
              </div>

              {/* Linked Registration Association */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-blue-600" />
                    State Registration Match (Vahan Database Lookup)
                  </h4>
                  {activeCase.linkedPerson?.identityVerified ? (
                    <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                      <Check className="w-3 h-3" /> Verified Record
                    </span>
                  ) : activeCase.plateMatch?.matchStatus === 'UNVERIFIED' ? (
                    <span className="text-[11px] font-semibold text-amber-800 bg-amber-100 px-2 py-0.5 rounded border border-amber-300">
                      Unverified Plate
                    </span>
                  ) : activeCase.plateMatch?.matchStatus === 'MANUAL_REQUIRED' ? (
                    <span className="text-[11px] font-semibold text-rose-800 bg-rose-100 px-2 py-0.5 rounded border border-rose-300">
                      Manual Plate Review Required
                    </span>
                  ) : (
                    <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                      Unverified / Lookup Pending
                    </span>
                  )}
                </div>

                {activeCase.linkedPerson ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[11px]">Owner Name:</span>
                      <span className="font-bold text-slate-900">{activeCase.linkedPerson.fullName}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Vehicle Plate:</span>
                      <span className="font-mono font-bold text-slate-900 bg-white px-1.5 py-0.5 rounded border border-slate-200 inline-block">
                        {activeCase.linkedPerson.vehiclePlate}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Vehicle Model:</span>
                      <span className="text-slate-700">{activeCase.linkedPerson.vehicleModel}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Masked Mobile:</span>
                      <span className="font-mono text-slate-700">{activeCase.linkedPerson.maskedMobile}</span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-500 italic">
                      {activeCase.plateMatch?.normalizedPlate 
                        ? `License plate OCR resolved as "${activeCase.plateMatch.normalizedPlate}", but no matching registration exists in the state database.`
                        : 'Plate obscured, unreadable, or not found in state vehicle registry.'}
                    </div>
                    <div className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 p-2.5 rounded-lg flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Manual Review Mandated:</strong> Automated challan issuance without verified vehicle registration is strictly prohibited. The reviewer must conduct manual registration verification or reject unverified candidates.
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Audit Timeline / Review History */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <History className="w-3.5 h-3.5 text-slate-500" />
                  Review Audit Trail
                </h4>
                <div className="space-y-1.5 max-h-36 overflow-y-auto">
                  {activeCase.reviewHistory.map((audit, i) => (
                    <div key={audit.id || i} className="p-2.5 rounded-lg border border-slate-200 bg-slate-50/50 text-xs flex items-start justify-between gap-2">
                      <div>
                        <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                          <span>{audit.action.replace('_', ' ')}</span>
                          <span className="text-slate-400">•</span>
                          <span className="text-slate-600 font-normal">{audit.actor}</span>
                        </div>
                        {audit.notes && (
                          <div className="text-slate-600 text-[11px] mt-0.5 italic">"{audit.notes}"</div>
                        )}
                        {audit.reason && (
                          <div className="text-rose-700 text-[11px] mt-0.5 font-medium">Reason: {audit.reason}</div>
                        )}
                      </div>
                      <span className="text-[10px] text-slate-400 whitespace-nowrap">{audit.timestamp}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Review Actions Panel */}
              <div className="pt-4 border-t border-slate-200 space-y-3">
                {activeCase.status === 'PENDING_REVIEW' ? (
                  <>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Reviewer Notes / Evidence Observations:
                      </label>
                      <input
                        type="text"
                        value={reviewerNotes}
                        onChange={e => setReviewerNotes(e.target.value)}
                        placeholder="Enter visual confirmation details or reasons before approving/rejecting..."
                        className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                      <div className="text-[11px] text-slate-400">
                        Due-process protocol active. Independent decision logged to immutable audit trail.
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleOpenRejectDialog}
                          disabled={Boolean(actionLoadingCaseId)}
                          className="px-4 py-2 text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject Candidate Case</span>
                        </button>

                        <button
                          type="button"
                          onClick={handleOpenApproveDialog}
                          disabled={Boolean(actionLoadingCaseId)}
                          className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-1.5 shadow-xs disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve Challan Draft</span>
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className={`p-4 rounded-xl border flex items-start gap-3 ${
                    activeCase.status === 'DRAFT_CREATED'
                      ? 'bg-blue-50/80 border-blue-200 text-blue-950'
                      : 'bg-rose-50/80 border-rose-200 text-rose-950'
                  }`}>
                    <Lock className="w-4 h-4 shrink-0 mt-0.5" />
                    <div className="text-xs space-y-1">
                      <div className="font-bold flex items-center gap-2">
                        <span>
                          {activeCase.status === 'DRAFT_CREATED'
                            ? 'Case Approved: Provisional Challan Draft Initiated'
                            : 'Case Evaluated: Candidate Rejected'}
                        </span>
                        <StatusBadge status={activeCase.status} size="sm" />
                      </div>
                      <p className="text-[11px] leading-relaxed opacity-90">
                        {activeCase.status === 'DRAFT_CREATED'
                          ? `Draft #${activeCase.challanDraftNumber || 'RECORDED'} has been registered for this rider. Review decisions are independent and do not cascade across other co-riders.`
                          : 'This candidate case has been rejected with documented cause in the audit history. Status is locked from further review changes.'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-xs">
              <EmptyState
                title="No Case Selected"
                description="Select a candidate case from the queue on the left to inspect bounding boxes and record reviewer findings."
              />
            </div>
          )}
        </div>
      </div>

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={dialogState.isOpen}
        onClose={() => {
          if (!actionLoadingCaseId) {
            setDialogState(prev => ({ ...prev, isOpen: false }));
          }
        }}
        onConfirm={handleConfirmAction}
        type={dialogState.type}
        title={dialogState.type === 'APPROVE_DRAFT' ? 'Confirm Challan Draft Creation' : 'Reject Candidate Detection'}
        caseId={dialogState.caseId}
        isLoading={Boolean(actionLoadingCaseId)}
      />
    </div>
  );
};
