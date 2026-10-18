import React, { useState } from 'react';
import { 
  Eye, 
  EyeOff, 
  ZoomIn, 
  RotateCcw, 
  Camera, 
  Sparkles,
  Info,
  AlertTriangle,
  Loader2,
  Layers
} from 'lucide-react';
import type { ViolationCase } from '../../types';
import { StatusBadge } from './StatusBadge';
import { getMediaUrl } from '../../services/api';
import { EvidenceCropImage } from './EvidenceCropImage';

interface EvidenceViewerProps {
  caseData: ViolationCase;
  showDetails?: boolean;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ 
  caseData, 
  showDetails = true 
}) => {
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null);
  const [isMainImageLoading, setIsMainImageLoading] = useState<boolean>(true);
  const [mainImageError, setMainImageError] = useState<boolean>(false);

  const handleZoomToggle = () => {
    setZoomLevel(prev => (prev === 1 ? 1.5 : prev === 1.5 ? 2.0 : 1));
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
    setSelectedBoxId(null);
  };

  const resolvedEvidenceUrl = getMediaUrl(caseData.evidenceImageUrl);
  const ridersWithCrops = (caseData.riders || []).filter(r => Boolean(r.cropPath));
  const effectiveRiderCrops = ridersWithCrops.length > 0 
    ? ridersWithCrops 
    : (caseData.riderCropUrl ? [{
        detectionId: caseData.riderDetails?.detectionId || 'rider-1',
        label: 'Rider Crop',
        classification: caseData.riderDetails?.classification || 'WITHOUT_HELMET',
        confidence: caseData.riderDetails?.confidence || caseData.confidence,
        bbox: (caseData.riderDetails?.bbox || [0, 0, 0, 0]) as [number, number, number, number],
        normalized: (caseData.riderDetails?.normalized || [0, 0, 0, 0]) as [number, number, number, number],
        cropPath: caseData.riderCropUrl,
        isViolation: true
      }] : []);

  const hasPlateCrop = Boolean(caseData.plateMatch?.cropPath);
  const hasRiderCrops = effectiveRiderCrops.length > 0;
  const showPlateFallback = !hasRiderCrops && hasPlateCrop;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs space-y-0">
      {/* Top Evidence Controls Bar */}
      <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Camera className="w-4 h-4 text-slate-500" />
          <span className="text-xs font-semibold text-slate-800">
            {caseData.camera.name}
          </span>
          <span className="text-xs text-slate-400">|</span>
          <span className="text-xs text-slate-500">
            {caseData.camera.location}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge status={caseData.evidenceQuality} size="sm" />
          
          <button
            type="button"
            onClick={() => setShowBoxes(!showBoxes)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md font-medium border transition-colors ${
              showBoxes 
                ? 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100' 
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
            title="Toggle AI Detection Bounding Boxes"
          >
            {showBoxes ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>{showBoxes ? 'Overlay On' : 'Overlay Off'}</span>
          </button>

          <button
            type="button"
            onClick={handleZoomToggle}
            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md font-medium bg-white text-slate-700 border border-slate-200 hover:bg-slate-50"
            title="Cycle Zoom Level"
          >
            <ZoomIn className="w-3.5 h-3.5" />
            <span>{zoomLevel}x</span>
          </button>

          {zoomLevel > 1 && (
            <button
              type="button"
              onClick={handleResetZoom}
              className="p-1 text-slate-500 hover:text-slate-700 rounded-md hover:bg-slate-100"
              title="Reset Zoom"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Image Stage */}
      <div className="relative w-full aspect-16/10 bg-slate-900 overflow-hidden flex items-center justify-center">
        {/* Loading Spinner */}
        {isMainImageLoading && !mainImageError && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900 text-slate-400 text-xs gap-2 z-10">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            <span>Loading primary evidence image...</span>
          </div>
        )}

        {/* Explicit Error Fallback */}
        {mainImageError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950 text-white p-6 text-center z-10 space-y-2">
            <AlertTriangle className="w-8 h-8 text-rose-500" />
            <div className="font-bold text-sm text-rose-300">Evidence Frame Failed to Load</div>
            <div className="text-xs text-slate-400 max-w-sm">
              The original surveillance capture could not be retrieved from the server.
            </div>
            <div className="font-mono text-[11px] text-slate-400 bg-slate-900 px-2 py-1 rounded border border-slate-800 break-all max-w-md">
              {resolvedEvidenceUrl || caseData.evidenceImageUrl}
            </div>
            <button
              type="button"
              onClick={() => {
                setMainImageError(false);
                setIsMainImageLoading(true);
              }}
              className="mt-2 px-3 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700"
            >
              Retry
            </button>
          </div>
        )}

        <div 
          className="relative w-full h-full transition-transform duration-200 ease-out origin-center select-none"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          {resolvedEvidenceUrl && (
            <img
              src={resolvedEvidenceUrl}
              alt={`Evidence for case ${caseData.id}`}
              onLoad={() => {
                setIsMainImageLoading(false);
                setMainImageError(false);
              }}
              onError={() => {
                setIsMainImageLoading(false);
                setMainImageError(true);
              }}
              className="w-full h-full object-cover"
            />
          )}

          {/* Interactive Bounding Boxes Overlay */}
          {showBoxes && !mainImageError && caseData.boundingBoxes && caseData.boundingBoxes.map(box => {
            const isSelected = selectedBoxId === box.id;
            const isNoHelmet = box.label === 'Without Helmet' || box.label === 'NO_HELMET' || box.label === 'WITHOUT_HELMET';

            return (
              <div
                key={box.id}
                onClick={() => setSelectedBoxId(isSelected ? null : box.id)}
                style={{
                  left: `${box.x}%`,
                  top: `${box.y}%`,
                  width: `${box.width}%`,
                  height: `${box.height}%`,
                  borderColor: isNoHelmet ? '#DC2626' : box.color || '#2563EB',
                }}
                className={`absolute border-2 cursor-pointer transition-all ${
                  isSelected ? 'border-amber-400 bg-amber-400/20 ring-2 ring-amber-400 ring-offset-1' : 'hover:bg-white/10'
                }`}
              >
                <div 
                  className="absolute -top-6 left-0 px-1.5 py-0.5 rounded text-[10px] font-bold tracking-tight text-white shadow-xs whitespace-nowrap flex items-center gap-1"
                  style={{ backgroundColor: isNoHelmet ? '#DC2626' : box.color || '#2563EB' }}
                >
                  <span>{box.label.replace('_', ' ')}</span>
                  <span>{(box.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Timestamp Stamp in lower right */}
        <div className="absolute bottom-2.5 right-3 bg-black/75 backdrop-blur-xs text-white font-mono text-[11px] px-2.5 py-1 rounded border border-white/10 z-10">
          REC: {caseData.timestamp}
        </div>
      </div>

      {/* Detected Crops Section in Case Detail */}
      {(hasRiderCrops || showPlateFallback) && (
        <div className="p-4 bg-slate-50 border-t border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-blue-600" />
              {hasRiderCrops ? 'Isolated Rider Evidence Crop' : 'Plate Fallback Evidence Crop'}
            </h4>
            <span className="text-[11px] text-slate-500 font-medium">
              {hasRiderCrops
                ? `${effectiveRiderCrops.length} Rider Crop(s)`
                : 'Manual Plate Review Fallback'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {/* Rider Crops */}
            {effectiveRiderCrops.map((r, idx) => (
              <EvidenceCropImage
                key={r.detectionId || idx}
                src={r.cropPath}
                alt={r.label}
                label={`Rider Evidence #${idx + 1}`}
                subtitle={r.detectionId}
                confidence={r.confidence}
                aspectRatio="aspect-square"
                badge={
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    r.classification === 'WITHOUT_HELMET'
                      ? 'bg-rose-100 text-rose-800 border border-rose-300'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  }`}>
                    {r.classification === 'WITHOUT_HELMET' ? 'NO HELMET' : 'WITH HELMET'}
                  </span>
                }
              />
            ))}

            {/* License Plate Fallback Crop (Only rendered when no rider crops exist) */}
            {showPlateFallback && (
              <EvidenceCropImage
                src={caseData.plateMatch?.cropPath}
                alt={caseData.plateMatch?.normalizedPlate || 'License Plate'}
                label="License Plate Fallback"
                subtitle={caseData.plateMatch?.normalizedPlate || 'Unread Plate'}
                confidence={caseData.plateMatch?.confidence}
                aspectRatio="aspect-square"
                badge={
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300">
                    MANUAL REVIEW FALLBACK
                  </span>
                }
              />
            )}
          </div>
        </div>
      )}

      {/* Box details and confidence strip */}
      {showDetails && (
        <div className="p-3.5 bg-slate-50/80 border-t border-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <span className="font-semibold text-slate-700">Predicted Type:</span>
              <span className="font-medium text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                {caseData.violationType.replace(/_/g, ' ')}
              </span>
              <span className="text-slate-400">|</span>
              <span className="font-semibold text-slate-700">Confidence:</span>
              <span className={`font-bold ${caseData.confidence >= 0.9 ? 'text-emerald-700' : 'text-amber-700'}`}>
                {(caseData.confidence * 100).toFixed(1)}%
              </span>
            </div>

            <div className="flex items-center gap-2 text-slate-500 text-[11px]">
              <Info className="w-3.5 h-3.5 text-slate-400" />
              <span>Bounding boxes represent candidate regions detected by Roboflow/YOLO engine.</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
