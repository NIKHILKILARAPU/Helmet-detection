import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Camera, 
  Video, 
  Play, 
  Square, 
  Sparkles, 
  AlertCircle, 
  CheckCircle2, 
  HelpCircle, 
  Radio
} from 'lucide-react';
import { useApp } from '../../context';
import { cameraService } from '../../services/cameraService';
import type { CameraDevice } from '../../services/cameraService';

export const CameraOperatorPage: React.FC = () => {
  const { addNewCapturedCase, addToast } = useApp();

  const videoRef = useRef<HTMLVideoElement>(null);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [availableDevices, setAvailableDevices] = useState<CameraDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('default');
  const [selectedSourceType, setSelectedSourceType] = useState<'WEBCAM' | 'IP_CAMERA' | 'CCTV_STREAM'>('WEBCAM');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [recentCaptures, setRecentCaptures] = useState<{ id: string; url: string; time: string; outcome: string }[]>([]);
  const [lastDetectionResult, setLastDetectionResult] = useState<{
    status: 'HELMET_DETECTED' | 'NO_HELMET_CANDIDATE' | 'UNCERTAIN' | 'NO_DETECTION';
    confidence: number;
    violationType?: string;
    caseId?: string;
    savedToQueue: boolean;
  } | null>(null);

  // Load available media devices
  useEffect(() => {
    cameraService.getAvailableVideoDevices().then(devices => {
      setAvailableDevices(devices);
      if (devices.length > 0) {
        setSelectedDeviceId(devices[0].deviceId);
      }
    });

    // Cleanup camera stream when component unmounts
    return () => {
      cameraService.stopWebcam();
    };
  }, []);

  const handleStartCamera = async () => {
    setErrorMessage(null);
    if (!videoRef.current) return;

    try {
      await cameraService.startWebcam(videoRef.current, selectedDeviceId);
      setIsStreaming(true);
      addToast({
        type: 'success',
        title: 'Camera Initialized',
        message: 'Local webcam stream active at 1280x720 30 FPS.'
      });
    } catch (err: any) {
      setIsStreaming(false);
      let msg = 'Failed to access camera device.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Camera permission was denied. Please allow camera permissions in your browser bar.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No video capture hardware was detected on your machine.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        msg = 'Camera is already in use by another application.';
      }
      setErrorMessage(msg);
      addToast({
        type: 'error',
        title: 'Camera Access Error',
        message: msg
      });
    }
  };

  const handleStopCamera = useCallback(() => {
    cameraService.stopWebcam();
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
    addToast({
      type: 'info',
      title: 'Camera Stream Stopped',
      message: 'Video hardware resources released.'
    });
  }, [addToast]);

  // Capture frame from webcam or generate simulated traffic frame
  const handleCaptureFrame = () => {
    setIsCapturing(true);
    setErrorMessage(null);

    let snapshotUrl: string | null = null;
    if (isStreaming && videoRef.current) {
      try {
        snapshotUrl = cameraService.captureFrame(videoRef.current);
      } catch (err: any) {
        setErrorMessage('Failed to capture video buffer: ' + err.message);
        setIsCapturing(false);
        return;
      }
    }

    // Run honest AI candidate simulation boundary
    setTimeout(() => {
      const sourceLabel = selectedSourceType === 'WEBCAM' 
        ? 'Laptop Operator Webcam' 
        : selectedSourceType === 'IP_CAMERA' 
          ? 'MG Road IP Cam 01' 
          : 'Koramangala CCTV Stream';

      const { candidateCase, outcomeType } = cameraService.simulateCandidateDetection(
        snapshotUrl, 
        sourceLabel
      );

      // Ingest into reviewer queue
      addNewCapturedCase(candidateCase);

      const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

      setRecentCaptures(prev => [
        {
          id: candidateCase.id,
          url: candidateCase.evidenceImageUrl,
          time: nowTime,
          outcome: outcomeType
        },
        ...prev.slice(0, 5)
      ]);

      setLastDetectionResult({
        status: outcomeType,
        confidence: candidateCase.confidence,
        violationType: candidateCase.violationType,
        caseId: candidateCase.id,
        savedToQueue: true
      });

      setIsCapturing(false);
    }, 400);
  };

  return (
    <div className="space-y-5">
      {/* Top Banner Notice */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Radio className="w-5 h-5 text-emerald-600 animate-pulse" />
            Live Surveillance Feed &amp; Edge Inference Workstation
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Test video capture from integrated laptop webcam or simulate network CCTV/IP camera feeds.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-medium border border-slate-200">
            <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-emerald-500' : 'bg-slate-400'}`} />
            <span>Feed: {isStreaming ? 'STREAMING ACTIVE' : 'STANDBY'}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-medium border border-purple-200">
            <Sparkles className="w-3.5 h-3.5 text-purple-600" />
            <span>AI: Demo Simulation Boundary</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Left Video Player & Controls (7 Cols), Right AI Results & Queue Panel (5 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Video Area & Device Selection (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {/* Controls toolbar */}
          <div className="p-3.5 border-b border-slate-200 bg-slate-50/70 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold text-slate-700">Source:</label>
              <select
                value={selectedSourceType}
                onChange={e => {
                  if (isStreaming) handleStopCamera();
                  setSelectedSourceType(e.target.value as any);
                }}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 font-medium focus:outline-hidden focus:ring-1 focus:ring-blue-500"
              >
                <option value="WEBCAM">Laptop Integrated Webcam</option>
                <option value="IP_CAMERA">IP Camera (MG Road Jn - RTSP Stream)</option>
                <option value="CCTV_STREAM">CCTV (Koramangala 80ft Road)</option>
              </select>
            </div>

            {selectedSourceType === 'WEBCAM' && availableDevices.length > 1 && (
              <select
                value={selectedDeviceId}
                onChange={e => setSelectedDeviceId(e.target.value)}
                disabled={isStreaming}
                className="text-xs px-2 py-1 rounded-md border border-slate-300 bg-white text-slate-700 disabled:opacity-50"
              >
                {availableDevices.map(d => (
                  <option key={d.deviceId} value={d.deviceId}>{d.label}</option>
                ))}
              </select>
            )}

            <div className="flex items-center gap-2">
              {!isStreaming ? (
                <button
                  type="button"
                  onClick={handleStartCamera}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors shadow-xs"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>Start Camera</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStopCamera}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg transition-colors shadow-xs"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>Stop Stream</span>
                </button>
              )}
            </div>
          </div>

          {/* Camera Stage */}
          <div className="relative w-full aspect-16/10 bg-slate-950 flex items-center justify-center overflow-hidden">
            {/* Live Video Element */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${isStreaming ? 'block' : 'hidden'}`}
            />

            {/* Standby Neutral Placeholder when camera is off */}
            {!isStreaming && (
              <div className="text-center p-8 max-w-sm">
                <div className="w-14 h-14 rounded-full bg-slate-800 text-slate-400 mx-auto flex items-center justify-center mb-3">
                  <Camera className="w-7 h-7" />
                </div>
                <h4 className="text-sm font-bold text-slate-200">
                  {selectedSourceType === 'WEBCAM' ? 'Webcam in Standby' : 'Network Stream Standby'}
                </h4>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  {selectedSourceType === 'WEBCAM' 
                    ? 'Click "Start Camera" above to activate your laptop webcam for real-time capture testing.'
                    : 'Network feed connection configured. Click "Capture Frame" to test detection pipeline with simulated traffic frames.'}
                </p>
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={handleStartCamera}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-xs"
                  >
                    <Video className="w-4 h-4" />
                    <span>Initialize Video Hardware</span>
                  </button>
                </div>
              </div>
            )}

            {/* Error Message Overlay */}
            {errorMessage && (
              <div className="absolute inset-x-4 bottom-4 p-3 bg-red-950/90 border border-red-500/50 rounded-lg text-white text-xs flex items-start gap-2.5 backdrop-blur-xs">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div className="flex-1">{errorMessage}</div>
              </div>
            )}

            {/* Live Camera HUD Indicators */}
            {isStreaming && (
              <div className="absolute top-3 left-3 flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-black/70 text-emerald-400 font-mono text-[11px] font-bold border border-emerald-500/40">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  REC LIVE
                </span>
                <span className="px-2 py-0.5 rounded bg-black/70 text-white font-mono text-[11px] border border-white/20">
                  30 FPS • 1080p
                </span>
              </div>
            )}
          </div>

          {/* Capture Trigger Bar */}
          <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-slate-500">
              Snapshot captures the current frame and dispatches it through the candidate analysis pipeline.
            </div>

            <button
              type="button"
              onClick={handleCaptureFrame}
              disabled={isCapturing}
              className="px-5 py-2.5 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-all flex items-center gap-2 shadow-xs disabled:opacity-50"
            >
              <Camera className="w-4 h-4" />
              <span>{isCapturing ? 'Analyzing Frame...' : 'Capture & Analyze Frame'}</span>
            </button>
          </div>
        </div>

        {/* Right: AI Detection Result & Recent Captures (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* AI Result Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-purple-600" />
                Inference Result Panel
              </h3>
              <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                SIMULATED BOUNDARY
              </span>
            </div>

            {lastDetectionResult ? (
              <div className="space-y-3">
                <div className="p-3.5 rounded-xl border flex items-center justify-between gap-3 bg-slate-50">
                  <div>
                    <span className="text-[11px] text-slate-400 block font-medium">Candidate Status:</span>
                    <div className="text-sm font-bold text-slate-900 mt-0.5">
                      {lastDetectionResult.status.replace(/_/g, ' ')}
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-[11px] text-slate-400 block font-medium">Confidence:</span>
                    <span className={`text-base font-bold ${
                      lastDetectionResult.confidence >= 0.9 ? 'text-emerald-700' : 'text-amber-700'
                    }`}>
                      {(lastDetectionResult.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="text-xs space-y-1.5 text-slate-600">
                  <div className="flex justify-between">
                    <span>Generated Case ID:</span>
                    <span className="font-mono font-bold text-slate-900">{lastDetectionResult.caseId}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Queue Ingestion:</span>
                    <span className="text-emerald-700 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Dispatched to Reviewer Desk
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <HelpCircle className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                <span>No frame analyzed yet. Click "Capture &amp; Analyze Frame" to test the detection result workflow.</span>
              </div>
            )}

            {/* Model & Hardware Telemetry strip */}
            <div className="p-3 rounded-lg bg-slate-50/80 border border-slate-200 text-xs space-y-1 text-slate-500">
              <div className="flex justify-between">
                <span>Model Backend:</span>
                <span className="font-medium text-slate-800">YOLOv8n-traffic (640x640)</span>
              </div>
              <div className="flex justify-between">
                <span>Inference Latency:</span>
                <span className="font-mono text-slate-800">~68 ms (Local GPU/NPU)</span>
              </div>
              <div className="flex justify-between">
                <span>Confidence Threshold:</span>
                <span className="font-mono text-slate-800">0.50 (Configurable)</span>
              </div>
            </div>
          </div>

          {/* Recent Captures Strip */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-3 flex items-center justify-between">
              <span>Recent Operator Frame Captures</span>
              <span className="text-[11px] font-normal text-slate-400">{recentCaptures.length} frames</span>
            </h3>

            {recentCaptures.length === 0 ? (
              <div className="text-xs text-slate-400 italic text-center py-4">
                Captured frames will appear here with thumbnail history.
              </div>
            ) : (
              <div className="space-y-2">
                {recentCaptures.map(c => (
                  <div key={c.id} className="p-2 rounded-lg border border-slate-200 flex items-center gap-3 bg-slate-50/50">
                    <img
                      src={c.url}
                      alt={c.id}
                      className="w-12 h-10 object-cover rounded border border-slate-300 bg-slate-900 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-xs text-slate-900">{c.id}</span>
                        <span className="text-[10px] text-slate-400">{c.time}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 truncate mt-0.5">
                        Outcome: {c.outcome.replace(/_/g, ' ')}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
