import React from 'react';
import { 
  AlertCircle, 
  CheckCircle2, 
  FileEdit, 
  XCircle, 
  ShieldCheck, 
  AlertTriangle 
} from 'lucide-react';
import type { ViolationStatus, EvidenceQuality, IdentityVerificationStatus } from '../../types';

interface StatusBadgeProps {
  status: ViolationStatus | EvidenceQuality | IdentityVerificationStatus | string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const isSm = size === 'sm';
  const sizeClasses = isSm ? 'text-xs px-2 py-0.5 gap-1' : 'text-xs px-2.5 py-1 gap-1.5 font-medium';

  switch (status) {
    case 'PENDING_REVIEW':
      return (
        <span className={`inline-flex items-center rounded-full bg-amber-50 text-amber-800 border border-amber-200 ${sizeClasses}`}>
          <AlertCircle className={isSm ? 'w-3 h-3 text-amber-600' : 'w-3.5 h-3.5 text-amber-600'} />
          <span>Pending Review</span>
        </span>
      );
    case 'DRAFT_CREATED':
      return (
        <span className={`inline-flex items-center rounded-full bg-blue-50 text-blue-800 border border-blue-200 ${sizeClasses}`}>
          <FileEdit className={isSm ? 'w-3 h-3 text-blue-600' : 'w-3.5 h-3.5 text-blue-600'} />
          <span>Draft Created</span>
        </span>
      );
    case 'REJECTED':
      return (
        <span className={`inline-flex items-center rounded-full bg-red-50 text-red-800 border border-red-200 ${sizeClasses}`}>
          <XCircle className={isSm ? 'w-3 h-3 text-red-600' : 'w-3.5 h-3.5 text-red-600'} />
          <span>Rejected</span>
        </span>
      );
    case 'REVIEWED':
      return (
        <span className={`inline-flex items-center rounded-full bg-green-50 text-green-800 border border-green-200 ${sizeClasses}`}>
          <CheckCircle2 className={isSm ? 'w-3 h-3 text-green-600' : 'w-3.5 h-3.5 text-green-600'} />
          <span>Verified &amp; Reviewed</span>
        </span>
      );
    case 'HIGH':
      return (
        <span className={`inline-flex items-center rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 ${sizeClasses}`}>
          <ShieldCheck className={isSm ? 'w-3 h-3 text-emerald-600' : 'w-3.5 h-3.5 text-emerald-600'} />
          <span>High Quality</span>
        </span>
      );
    case 'MEDIUM':
      return (
        <span className={`inline-flex items-center rounded-md bg-yellow-50 text-yellow-800 border border-yellow-200 ${sizeClasses}`}>
          <AlertTriangle className={isSm ? 'w-3 h-3 text-yellow-600' : 'w-3.5 h-3.5 text-yellow-600'} />
          <span>Medium Quality</span>
        </span>
      );
    case 'LOW':
      return (
        <span className={`inline-flex items-center rounded-md bg-rose-50 text-rose-800 border border-rose-200 ${sizeClasses}`}>
          <AlertCircle className={isSm ? 'w-3 h-3 text-rose-600' : 'w-3.5 h-3.5 text-rose-600'} />
          <span>Low Quality</span>
        </span>
      );
    case 'VERIFIED':
      return (
        <span className={`inline-flex items-center rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 ${sizeClasses}`}>
          <CheckCircle2 className={isSm ? 'w-3 h-3 text-emerald-600' : 'w-3.5 h-3.5 text-emerald-600'} />
          <span>Verified Record</span>
        </span>
      );
    case 'MANUAL_REQUIRED':
      return (
        <span className={`inline-flex items-center rounded-full bg-amber-50 text-amber-800 border border-amber-200 ${sizeClasses}`}>
          <AlertTriangle className={isSm ? 'w-3 h-3 text-amber-600' : 'w-3.5 h-3.5 text-amber-600'} />
          <span>Manual Check Req.</span>
        </span>
      );
    default:
      return (
        <span className={`inline-flex items-center rounded-full bg-slate-100 text-slate-700 border border-slate-200 ${sizeClasses}`}>
          <span>{status}</span>
        </span>
      );
  }
};
