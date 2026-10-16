import React, { useState } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Search, 
  FileCheck2, 
  User, 
  History, 
  Check 
} from 'lucide-react';
import { useApp } from '../../context';
import type { ViolationStatus } from '../../types';
import { EvidenceViewer } from '../common/EvidenceViewer';
import { StatusBadge } from '../common/StatusBadge';
import { ConfirmationDialog } from '../common/ConfirmationDialog';
import { EmptyState } from '../common/EmptyState';

export const ReviewerQueue: React.FC = () => {
  const { cases, approveDraft, rejectCase } = useApp();

  const [activeTab, setActiveTab] = useState<ViolationStatus | 'ALL'>('PENDING_REVIEW');
  const [selectedCaseId, setSelectedCaseId] = useState<string>(
    cases.find(c => c.status === 'PENDING_REVIEW')?.id || cases[0]?.id || ''
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [reviewerNotes, setReviewerNotes] = useState('');
  
  // Dialog state
  const [dialogState, setDialogState] = useState<{
    isOpen: boolean;
    type: 'APPROVE_DRAFT' | 'REJECT_CASE';
    caseId?: string;
  }>({
    isOpen: false,
    type: 'APPROVE_DRAFT'
  });

  // Filter cases
  const filteredCases = cases.filter(c => {
    const matchesTab = activeTab === 'ALL' || c.status === activeTab;
    const matchesSearch = 
      searchQuery.trim() === '' ||
      c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.camera.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.linkedPerson?.vehiclePlate.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesTab && matchesSearch;
  });

  const activeCase = cases.find(c => c.id === selectedCaseId) || filteredCases[0] || null;

  const handleOpenApproveDialog = () => {
    if (!activeCase) return;
    setDialogState({
      isOpen: true,
      type: 'APPROVE_DRAFT',
      caseId: activeCase.id
    });
  };

  const handleOpenRejectDialog = () => {
    if (!activeCase) return;
    setDialogState({
      isOpen: true,
      type: 'REJECT_CASE',
      caseId: activeCase.id
    });
  };

  const handleConfirmAction = (notes?: string, reason?: string) => {
    if (!activeCase) return;

    if (dialogState.type === 'APPROVE_DRAFT') {
      approveDraft(activeCase.id, notes || reviewerNotes);
      setReviewerNotes('');
    } else if (dialogState.type === 'REJECT_CASE') {
      rejectCase(activeCase.id, reason || 'FALSE_DETECTION_SHADOW', notes || reviewerNotes);
      setReviewerNotes('');
    }
  };

  return (
    <div className="space-y-4">
      {/* Reviewer Header & Guidance Notice */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-blue-600" />
            Candidate Evidence Review &amp; Draft Verification Desk
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Human-in-the-loop verification under Section 129 Motor Vehicles Act. Approval creates a provisional draft only.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold text-slate-700">Queue Metrics:</span>
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold">
            {cases.filter(c => c.status === 'PENDING_REVIEW').length} Pending
          </span>
          <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-bold">
            {cases.filter(c => c.status === 'DRAFT_CREATED').length} Drafts
          </span>
        </div>
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

                      <div className="text-right">
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
                      <span className="font-mono text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded text-[11px]">
                        {item.linkedPerson?.vehiclePlate || 'Unmatched'}
                      </span>
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
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-slate-900 font-mono">
                      {activeCase.id}
                    </h3>
                    <StatusBadge status={activeCase.status} size="md" />
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

              {/* Evidence Viewer Stage with Bounding Boxes */}
              <EvidenceViewer caseData={activeCase} showDetails={true} />

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
                  <div className="text-xs text-slate-500 italic">
                    Plate obscured or not found in state vehicle registry. Requires manual registration inquiry.
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
                    Due-process protocol active. All decisions logged to immutable audit trail.
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleOpenRejectDialog}
                      className="px-4 py-2 text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Reject Candidate Case</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleOpenApproveDialog}
                      className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-1.5 shadow-xs"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Approve Challan Draft</span>
                    </button>
                  </div>
                </div>
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
        onClose={() => setDialogState(prev => ({ ...prev, isOpen: false }))}
        onConfirm={handleConfirmAction}
        type={dialogState.type}
        title={dialogState.type === 'APPROVE_DRAFT' ? 'Confirm Challan Draft Creation' : 'Reject Candidate Detection'}
        caseId={dialogState.caseId}
      />
    </div>
  );
};
