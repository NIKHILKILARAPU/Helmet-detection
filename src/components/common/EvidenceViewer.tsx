import React, { useState } from 'react';
import { 
  Eye, 
  EyeOff, 
  ZoomIn, 
  RotateCcw, 
  Camera, 
  Sparkles,
  Info
} from 'lucide-react';
import type { ViolationCase } from '../../types';
import { StatusBadge } from './StatusBadge';

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

  const handleZoomToggle = () => {
    setZoomLevel(prev => (prev === 1 ? 1.5 : prev === 1.5 ? 2.0 : 1));
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
    setSelectedBoxId(null);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
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
        <div 
          className="relative w-full h-full transition-transform duration-200 ease-out origin-center select-none"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          <img
            src={caseData.evidenceImageUrl}
            alt={`Evidence for case ${caseData.id}`}
            className="w-full h-full object-cover"
          />

          {/* Interactive Bounding Boxes Overlay */}
          {showBoxes && caseData.boundingBoxes && caseData.boundingBoxes.map(box => {
            const isSelected = selectedBoxId === box.id;
            const isNoHelmet = box.label === 'NO_HELMET';

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
        <div className="absolute bottom-2.5 right-3 bg-black/75 backdrop-blur-xs text-white font-mono text-[11px] px-2.5 py-1 rounded border border-white/10">
          REC: {caseData.timestamp}
        </div>
      </div>

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
              <span>Bounding boxes represent candidate regions detected by YOLO model.</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
