import React, { useState } from 'react';
import { 
  Car, 
  AlertTriangle, 
  Phone, 
  Mail, 
  CheckCircle2, 
  HelpCircle, 
  Send, 
  Eye, 
  Info 
} from 'lucide-react';
import { useApp } from '../../context';
import { StatusBadge } from '../common/StatusBadge';
import { Modal } from '../common/Modal';
import { EvidenceViewer } from '../common/EvidenceViewer';
import { personService } from '../../services/personService';
import type { ViolationCase } from '../../types';

export const CitizenPortal: React.FC = () => {
  const { persons, cases, addToast } = useApp();

  // Active citizen demo account (Aditya Sharma)
  const citizen = persons.find(p => p.personId === 'PID-77319') || persons[0];

  // Cases associated with this citizen's vehicles
  const citizenCases = cases.filter(c => 
    c.linkedPerson?.personId === citizen.personId ||
    citizen.linkedVehicles.some(v => v.plateNumber === c.linkedPerson?.vehiclePlate)
  );

  const [selectedCaseForReview, setSelectedCaseForReview] = useState<ViolationCase | null>(null);
  const [disputeModalOpen, setDisputeModalOpen] = useState(false);
  const [disputeTargetCase, setDisputeTargetCase] = useState<ViolationCase | null>(null);
  const [disputeReason, setDisputeReason] = useState('NOT_MY_VEHICLE');
  const [disputeComments, setDisputeComments] = useState('');
  const [isSubmittingDispute, setIsSubmittingDispute] = useState(false);

  const handleOpenDispute = (c: ViolationCase) => {
    setDisputeTargetCase(c);
    setDisputeModalOpen(true);
  };

  const handleSubmitDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disputeTargetCase) return;

    setIsSubmittingDispute(true);
    try {
      const res = await personService.reportMismatch(
        citizen.personId,
        disputeTargetCase.id,
        disputeReason,
        disputeComments
      );

      addToast({
        type: 'success',
        title: 'Review Request Submitted',
        message: `${res.message} Dispute Tracking ID: ${res.disputeId}`
      });

      setDisputeModalOpen(false);
      setDisputeComments('');
    } finally {
      setIsSubmittingDispute(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Important Legal Notice Banner */}
      <div className="rounded-xl bg-blue-50 border border-blue-200 p-4 shadow-xs flex items-start gap-3">
        <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="text-xs text-blue-900 leading-relaxed">
          <strong className="font-semibold block text-sm mb-1">
            Official Citizen Advisory: Provisional Observations Notice
          </strong>
          Any safety observation displayed on this portal is a candidate detection currently undergoing human officer verification. 
          <strong> A pending detection is NOT an official fine or a legal determination of guilt.</strong> You have the legal right under traffic regulations to review the evidence and request verification if a vehicle or person record was incorrectly associated.
        </div>
      </div>

      {/* Citizen Identity & Vehicle Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Left: Citizen Profile (1 Col) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-base shadow-xs">
              {citizen.fullName.charAt(0)}
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 leading-tight">
                {citizen.fullName}
              </h2>
              <span className="text-xs text-slate-500 font-mono">
                {citizen.personId}
              </span>
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-slate-100 text-xs">
            <div className="flex items-center justify-between text-slate-600">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Phone className="w-3.5 h-3.5" /> Masked Contact:
              </span>
              <span className="font-mono font-semibold text-slate-800">{citizen.maskedMobile}</span>
            </div>
            <div className="flex items-center justify-between text-slate-600">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Mail className="w-3.5 h-3.5" /> Email:
              </span>
              <span className="text-slate-800 truncate max-w-[170px]">{citizen.email}</span>
            </div>
            <div className="flex items-center justify-between text-slate-600">
              <span className="text-slate-400">Identity Status:</span>
              <StatusBadge status={citizen.identityStatus} size="sm" />
            </div>
          </div>
        </div>

        {/* Right: Registered Vehicles Summary (2 Cols) */}
        <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <Car className="w-4 h-4 text-blue-600" />
              Linked Two-Wheelers (State Vahan Database)
            </h3>
            <span className="text-xs text-slate-400">
              {citizen.linkedVehicles.length} vehicles registered
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            {citizen.linkedVehicles.map(v => (
              <div 
                key={v.plateNumber}
                className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/60 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs bg-white text-slate-900 px-2 py-0.5 rounded border border-slate-200">
                      {v.plateNumber}
                    </span>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {v.status}
                    </span>
                  </div>
                  <div className="text-xs font-semibold text-slate-800 mt-2">
                    {v.model}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {v.vehicleType}
                  </div>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-200/60 text-[10px] text-slate-400">
                  Registered: {v.registeredDate}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Observations & Notice History Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/60 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Your Traffic Safety Observations &amp; Notice Records
            </h3>
            <p className="text-xs text-slate-500">
              Complete history of camera observations linked to your registered plate number.
            </p>
          </div>
          <div className="text-xs text-slate-500">
            Total records: <strong>{citizenCases.length}</strong>
          </div>
        </div>

        {citizenCases.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
            <h4 className="font-bold text-slate-800">Clear Safety Record</h4>
            <p className="text-slate-500 mt-1">No candidate safety observations or drafts recorded for your vehicles.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Observation ID</th>
                  <th className="py-3 px-4">Date &amp; Time</th>
                  <th className="py-3 px-4">Location</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Vehicle</th>
                  <th className="py-3 px-4">Review Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {citizenCases.map(c => (
                  <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      {c.id}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">
                      {c.timestamp}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-slate-800">{c.camera.name}</div>
                      <div className="text-[11px] text-slate-400">{c.camera.location}</div>
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800">
                      {c.violationType.replace(/_/g, ' ')}
                    </td>
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-800">
                      {c.linkedPerson?.vehiclePlate}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={c.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => setSelectedCaseForReview(c)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>View Evidence</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleOpenDispute(c)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50"
                        title="Report incorrect person/vehicle match"
                      >
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                        <span>Report Mismatch</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Help & Support Desk */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
            <HelpCircle className="w-4 h-4 text-blue-600" />
            Questions or Legal Grievance Support?
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Traffic Police Grievance Redressal Cell is open Monday to Saturday, 09:00 AM - 06:00 PM IST.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <a 
            href="tel:1095" 
            className="px-3 py-1.5 font-bold rounded-lg bg-slate-100 text-slate-800 hover:bg-slate-200 transition-colors flex items-center gap-1.5"
          >
            <Phone className="w-3.5 h-3.5 text-slate-600" />
            <span>Traffic Helpline: 1095</span>
          </a>
        </div>
      </div>

      {/* Evidence Modal for Citizen */}
      {selectedCaseForReview && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedCaseForReview(null)}
          title={`Safety Observation Evidence: ${selectedCaseForReview.id}`}
          subtitle={`Recorded on ${selectedCaseForReview.timestamp} at ${selectedCaseForReview.camera.name}`}
          maxWidth="3xl"
        >
          <div className="space-y-4">
            <EvidenceViewer caseData={selectedCaseForReview} showDetails={true} />

            <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 leading-relaxed">
              <strong>Notice:</strong> This image was captured by an automated roadside surveillance camera. Bounding boxes show computer-assisted detection points. A qualified traffic officer must inspect the frame before any formal draft is sanctioned.
            </div>

            <div className="pt-2 flex justify-between items-center">
              <button
                type="button"
                onClick={() => {
                  const target = selectedCaseForReview;
                  setSelectedCaseForReview(null);
                  handleOpenDispute(target);
                }}
                className="text-xs font-bold text-amber-700 hover:text-amber-800 flex items-center gap-1"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Not your vehicle or incorrect rider? Report Mismatch &rarr;</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedCaseForReview(null)}
                className="px-4 py-2 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close Evidence
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Dispute / Report Mismatch Modal */}
      {disputeModalOpen && disputeTargetCase && (
        <Modal
          isOpen={true}
          onClose={() => setDisputeModalOpen(false)}
          title="Report Incorrect Record or Vehicle Match"
          subtitle={`Disputing Observation Case ID: ${disputeTargetCase.id}`}
          maxWidth="md"
        >
          <form onSubmit={handleSubmitDispute} className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-slate-700">
              <div className="font-semibold text-slate-900">Associated Vehicle:</div>
              <div className="font-mono text-sm font-bold text-blue-700 mt-0.5">
                {disputeTargetCase.linkedPerson?.vehiclePlate}
              </div>
            </div>

            <div>
              <label className="block font-semibold text-slate-800 mb-1.5">
                Please select the reason for dispute: <span className="text-red-500">*</span>
              </label>
              <select
                value={disputeReason}
                onChange={e => setDisputeReason(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              >
                <option value="NOT_MY_VEHICLE">Not my vehicle / Number plate reading error</option>
                <option value="WEARING_COMPLIANT_HELMET">Rider/Pillion was wearing a compliant helmet (glare/shadow error)</option>
                <option value="VEHICLE_SOLD_TRANSFERRED">Vehicle was sold/transferred prior to this date</option>
                <option value="VEHICLE_STOLEN">Vehicle was reported stolen at the time of observation</option>
                <option value="OTHER">Other circumstance (describe below)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-800 mb-1.5">
                Additional Comments / Evidence Reference:
              </label>
              <textarea
                value={disputeComments}
                onChange={e => setDisputeComments(e.target.value)}
                rows={3}
                placeholder="Provide details (e.g. colour of helmet worn, registration card reference, police theft complaint number)..."
                className="w-full text-xs rounded-lg border border-slate-300 p-3 text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="p-3 rounded-lg bg-blue-50 text-blue-900 text-[11px] leading-relaxed border border-blue-200">
              Submitting this dispute pauses automated draft workflows for this case and forwards the high-resolution frame to an enforcement review officer.
            </div>

            <div className="pt-2 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setDisputeModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmittingDispute}
                className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-1.5 shadow-xs disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSubmittingDispute ? 'Submitting...' : 'Submit Verification Request'}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
