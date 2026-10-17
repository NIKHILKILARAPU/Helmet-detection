
import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  RotateCcw, 
  ZoomIn, 
  ImageIcon, 
  Loader2, 
  ExternalLink 
} from 'lucide-react';
import { getMediaUrl, fetchAuthenticatedBlobUrl } from '../../services/api';
import { Modal } from './Modal';

export interface EvidenceCropImageProps {
  src?: string | null;
  alt: string;
  className?: string;
  aspectRatio?: string;
  label?: string;
  subtitle?: string;
  confidence?: number;
  badge?: React.ReactNode;
  allowEnlarge?: boolean;
  authenticated?: boolean;
  maxHeight?: string;
}

export const EvidenceCropImage: React.FC<EvidenceCropImageProps> = ({
  src,
  alt,
  className = '',
  aspectRatio = 'aspect-4/3',
  label,
  subtitle,
  confidence,
  badge,
  allowEnlarge = true,
  authenticated = false,
  maxHeight = 'max-h-52'
}) => {
  const resolvedUrl = getMediaUrl(src);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<'IDLE' | 'LOADING' | 'LOADED' | 'ERROR'>(() => 
    !src || !src.trim() ? 'IDLE' : 'LOADING'
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState<boolean>(false);
  const [retryCounter, setRetryCounter] = useState<number>(0);

  // Authenticated fetch if requested
  useEffect(() => {
    let isMounted = true;
    let localBlob: string | null = null;

    if (!src || !src.trim()) {
      return;
    }

    if (authenticated) {
      // Secure authenticated fetch (Bearer token strictly in Authorization header, never query param)
      fetchAuthenticatedBlobUrl(src)
        .then(url => {
          if (!isMounted) {
            URL.revokeObjectURL(url);
            return;
          }
          localBlob = url;
          setBlobUrl(url);
          setLoadStatus('LOADED');
        })
        .catch(err => {
          if (!isMounted) return;
          setLoadStatus('ERROR');
          setErrorMessage(err.message || 'Failed to authenticate and fetch evidence crop.');
        });
    }

    return () => {
      isMounted = false;
      if (localBlob) {
        URL.revokeObjectURL(localBlob);
      }
    };
  }, [src, authenticated, retryCounter]);

  // Clean up blob URL on unmount
  useEffect(() => {
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [blobUrl]);

  const handleRetry = (e: React.MouseEvent) => {
    e.stopPropagation();
    setLoadStatus('LOADING');
    setErrorMessage(null);
    setRetryCounter(prev => prev + 1);
  };

  const imageSource = blobUrl || resolvedUrl;

  return (
    <div className={`relative flex flex-col rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden ${className}`}>
      {/* Top Header Bar if label or badge provided */}
      {(label || badge || confidence !== undefined) && (
        <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/80 flex items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-1.5 min-w-0">
            {label && (
              <span className="font-bold text-slate-800 text-[11px] truncate">
                {label}
              </span>
            )}
            {subtitle && (
              <span className="text-[10px] text-slate-500 font-mono truncate">
                {subtitle}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {confidence !== undefined && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                confidence >= 0.85 
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                  : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}>
                {(confidence * 100).toFixed(0)}%
              </span>
            )}
            {badge}
          </div>
        </div>
      )}

      {/* Media Canvas Stage */}
      <div className={`relative w-full ${aspectRatio} ${maxHeight} bg-slate-900 flex items-center justify-center overflow-hidden group`}>
        {/* State 1: No crop available */}
        {(!src || !src.trim() || loadStatus === 'IDLE') && (
          <div className="p-4 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-1">
            <ImageIcon className="w-6 h-6 text-slate-600 mb-1" />
            <span className="font-semibold text-slate-300">No Crop Available</span>
            <span className="text-[10px] text-slate-500">Bounding region was too small or missing</span>
          </div>
        )}

        {/* State 2: Loading State with Spinner & Skeleton */}
        {src && loadStatus === 'LOADING' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 text-slate-300 gap-2 p-3 text-xs animate-pulse">
            <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
            <span className="text-[11px] font-medium text-slate-400">Loading evidence crop...</span>
            <span className="text-[9px] font-mono text-slate-500 truncate max-w-[200px]">
              {src.split('/').pop()}
            </span>
          </div>
        )}

        {/* State 3: Explicit Error State (Never silently hidden) */}
        {src && loadStatus === 'ERROR' && (
          <div className="absolute inset-0 p-3 bg-red-950/95 text-white flex flex-col items-center justify-center text-center gap-1.5 z-10">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            <div className="font-bold text-[11px] text-rose-200">
              Crop Image Unavailable
            </div>
            <div className="text-[10px] text-rose-300 leading-tight max-w-[240px]">
              {errorMessage || 'File not found on backend (404) or network request failed.'}
            </div>
            <div className="font-mono text-[9px] text-rose-400/80 bg-red-900/40 px-1.5 py-0.5 rounded border border-rose-800 truncate max-w-[220px]">
              {resolvedUrl || src}
            </div>
            <button
              type="button"
              onClick={handleRetry}
              className="mt-1 inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold text-white bg-rose-700 hover:bg-rose-600 rounded-md transition-colors shadow-xs"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Retry Load</span>
            </button>
          </div>
        )}

        {/* State 4: Image Rendered */}
        {src && loadStatus !== 'ERROR' && (
          <>
            <img
              src={imageSource}
              alt={alt}
              onLoad={() => setLoadStatus('LOADED')}
              onError={() => {
                setLoadStatus('ERROR');
                setErrorMessage('Browser failed to render image from backend origin.');
              }}
              className={`w-full h-full object-contain transition-opacity duration-200 ${
                loadStatus === 'LOADED' ? 'opacity-100' : 'opacity-0'
              }`}
            />

            {/* Click to Enlarge Hover Overlay */}
            {allowEnlarge && loadStatus === 'LOADED' && (
              <button
                type="button"
                onClick={() => setIsPreviewOpen(true)}
                className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-semibold gap-1.5 cursor-pointer backdrop-blur-2xs"
                title="Click to view enlarged evidence crop"
              >
                <ZoomIn className="w-4 h-4 text-white" />
                <span>Enlarge</span>
              </button>
            )}
          </>
        )}
      </div>

      {/* Path Stamp Footer */}
      {src && (
        <div className="px-2.5 py-1.5 bg-slate-50 border-t border-slate-100 text-[10px] text-slate-500 font-mono flex items-center justify-between gap-2">
          <span className="truncate" title={src}>
            {src.split('/').pop()}
          </span>
          {allowEnlarge && loadStatus === 'LOADED' && (
            <button
              type="button"
              onClick={() => setIsPreviewOpen(true)}
              className="text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-0.5 shrink-0"
            >
              <span>Inspect</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </button>
          )}
        </div>
      )}

      {/* Enlarged Inspection Modal */}
      {allowEnlarge && isPreviewOpen && (
        <Modal
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
          title={label || 'Evidence Crop Inspection'}
          subtitle={`Path: ${src || ''}`}
          maxWidth="lg"
        >
          <div className="space-y-4">
            <div className="bg-slate-950 rounded-xl p-2 flex items-center justify-center max-h-[70vh] overflow-hidden">
              <img
                src={imageSource}
                alt={alt}
                className="max-h-[65vh] w-auto object-contain rounded-lg shadow-lg"
              />
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="text-slate-400 block text-[10px]">Classification / Target:</span>
                <span className="font-semibold text-slate-900">{alt}</span>
              </div>
              {confidence !== undefined && (
                <div>
                  <span className="text-slate-400 block text-[10px]">Model Confidence:</span>
                  <span className="font-bold text-slate-900">{(confidence * 100).toFixed(1)}%</span>
                </div>
              )}
              <div>
                <span className="text-slate-400 block text-[10px]">Storage Location:</span>
                <span className="font-mono text-slate-700 text-[11px]">{src}</span>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
