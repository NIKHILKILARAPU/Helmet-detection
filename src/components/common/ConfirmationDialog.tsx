import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react';
import { Modal } from './Modal';

interface ConfirmationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (notes?: string, reason?: string) => void;
  title: string;
  type: 'APPROVE_DRAFT' | 'REJECT_CASE' | 'GENERIC_DANGER';
  caseId?: string;
  confirmButtonText?: string;
}

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  type,
  caseId,
  confirmButtonText
}) => {
  const [notes, setNotes] = useState('');
  const [reason, setReason] = useState('FALSE_DETECTION_SHADOW');

  const isApprove = type === 'APPROVE_DRAFT';
  const isReject = type === 'REJECT_CASE';

  const handleConfirm = () => {
    onConfirm(notes, reason);
    setNotes('');
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      subtitle={caseId ? `Target Case ID: ${caseId}` : undefined}
      maxWidth="md"
    >
      <div className="space-y-4">
        {/* Important Legal Boundary Notice */}
        {isApprove && (
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3.5 flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-900 leading-relaxed">
              <strong className="font-semibold block mb-0.5">Procedural Notice: Draft Creation Only</strong>
              Confirming this action creates a <strong>CHALLAN_DRAFT</strong> for formal verification. It does not determine legal guilt, issue an irrevocable fine, or execute automated payment charges.
            </div>
          </div>
        )}

        {isReject && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3.5 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="text-xs text-rose-900 leading-relaxed">
              <strong className="font-semibold block mb-0.5">Rejection Audit Record</strong>
              Rejecting this detection candidate archives the frame with an audit reason. The linked vehicle/person will receive no penalty notice.
            </div>
          </div>
        )}

        {/* Reason selector for rejection */}
        {isReject && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Select Primary Rejection Reason <span className="text-red-500">*</span>
            </label>
            <select
              value={reason}
              onChange={e => setReason(e.target.value)}
              className="w-full text-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="FALSE_DETECTION_SHADOW">Shadow or lighting illusion / false positive</option>
              <option value="COMPLIANT_HELMET_VERIFIED">Compliant helmet verified upon visual review</option>
              <option value="OCCLUDED_OR_LOW_QUALITY">Vehicle / headgear occluded or low image quality</option>
              <option value="REGISTRATION_PLATE_MISMATCH">Unclear or mismatched registration plate</option>
              <option value="EXEMPT_CATEGORY">Authorized exempt category / operational service</option>
              <option value="OTHER">Other administrative reason (specify below)</option>
            </select>
          </div>
        )}

        {/* Reviewer notes textarea */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Reviewer Remarks / Audit Notes {isApprove ? '(Optional)' : '(Recommended)'}
          </label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            placeholder={
              isApprove 
                ? 'e.g., Rider verified unhelmeted in lane 2. Clear plate visibility.' 
                : 'e.g., Lighting glare over helmet shell misled AI confidence threshold.'
            }
            className="w-full text-xs rounded-lg border border-slate-300 p-3 text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Action Buttons */}
        <div className="pt-2 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            className={`px-4 py-2 text-xs font-semibold text-white rounded-lg transition-colors flex items-center gap-1.5 shadow-xs ${
              isReject 
                ? 'bg-red-600 hover:bg-red-700 focus:ring-red-500' 
                : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
            }`}
          >
            {isReject ? <ShieldAlert className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
            <span>{confirmButtonText || (isReject ? 'Confirm Rejection' : 'Confirm Draft Approval')}</span>
          </button>
        </div>
      </div>
    </Modal>
  );
};
