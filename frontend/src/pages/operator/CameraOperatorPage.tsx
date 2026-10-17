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
  Radio,
  Upload,
  Key,
  ShieldAlert,
  Layers
} from 'lucide-react';
import { useApp } from '../../context';
import { cameraService } from '../../services/cameraService';
import { apiClient } from '../../services/api';
import type { CameraDevice } from '../../services/cameraService';
import type { BoundingBox, ViolationCase, DetectionAnalysisResult } from '../../types';

export const CameraOperatorPage: React.FC = () => {
  const { addNewCapturedCase, addToast, currentUser } = useApp();

  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [availableDevices, setAvailableDevices] = useState<CameraDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('default');
  const [selectedSourceType, setSelectedSourceType] = useState<'WEBCAM' | 'IP_CAMERA' | 'CCTV_STREAM'>('WEBCAM');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<any[]>([]);
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [capturedSnapshotUrl, setCapturedSnapshotUrl] = useState<string | null>(null);
  const [overlayBoxes, setOverlayBoxes] = useState<BoundingBox[]>([]);
  const [showOverlay, setShowOverlay] = useState<boolean>(true);

  // Model telemetry state
  const [modelStatus, setModelStatus] = useState<{
    provider?: string;
    isLoaded: boolean;
    classesCount: number;
    helmetClassificationSupported: boolean;
    modelPath?: string;
    modelId?: string;
    loadError?: string | null;
  } | null>(null);

  // Authentication token management state
  const [authToken, setAuthTokenState] = useState<string | null>(() => apiClient.getAuthToken());
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [authEmail, setAuthEmail] = useState<string>('admin@trafficguard.gov.in');
  const [authPassword, setAuthPassword] = useState<string>('');
  const [authManualToken, setAuthManualToken] = useState<string>('');
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  const [recentCaptures, setRecentCaptures] = useState<{ id: string; url: string; time: string; outcome: string }[]>([]);
  const [lastDetectionResult, setLastDetectionResult] = useState<{
    status: 'HELMET_DETECTED' | 'NO_HELMET_CANDIDATE' | 'UNCERTAIN' | 'NO_DETECTION' | 'COCO_OBJECTS_ONLY';
    confidence: number;
    violationType?: string;
    caseId?: string;
    savedToQueue: boolean;
    totalDetections: number;
    vehiclesCount: number;
    personsCount: number;
    processingTimeMs: number;
    helmetClassificationAvailable: boolean;
    helmetClassificationMessage: string;
    boxes: BoundingBox[];
  } | null>(null);

  // Fetch model status on component mount
  const checkModelStatus = useCallback(async () => {
    try {
      const res = await cameraService.getModelStatus();
      if (res.data) {
        setModelStatus(res.data);
      }
    } catch {
      // ignore
    }
  }, []);

  // Load available media devices and model status
  useEffect(() => {
    cameraService.getAvailableVideoDevices().then(devices => {
      setAvailableDevices(devices);
      if (devices.length > 0) {
        setSelectedDeviceId(devices[0].deviceId);
      }
    });

    checkModelStatus();

    // Cleanup camera stream when component unmounts
    return () => {
      cameraService.stopWebcam();
    };
  }, [checkModelStatus]);

  const handleStartCamera = async () => {
    setErrorMessage(null);
    setErrorDetails([]);
    if (!videoRef.current) return;

    try {
      await cameraService.startWebcam(videoRef.current, selectedDeviceId);
      setIsStreaming(true);
      setCapturedSnapshotUrl(null);
      setOverlayBoxes([]);
      addToast({
        type: 'success',
        title: 'Camera Initialized',
        message: 'Webcam feed active. Frames can now be captured and analyzed by YOLO.'
      });
    } catch (err: any) {
      setIsStreaming(false);
      let msg = 'Failed to access camera device.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Camera permission was denied. Please allow camera permissions in your browser.';
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

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggingIn(true);
    setErrorMessage(null);

    if (authManualToken.trim()) {
      apiClient.setAuthToken(authManualToken.trim());
      setAuthTokenState(authManualToken.trim());
      setShowAuthModal(false);
      setIsLoggingIn(false);
      addToast({
        type: 'success',
        title: 'JWT Token Saved',
        message: 'Authorization token registered for API inference requests.'
      });
      return;
    }

    const res = await apiClient.login(authEmail, authPassword);
    setIsLoggingIn(false);
    if (res.success && res.token) {
      setAuthTokenState(res.token);
      setShowAuthModal(false);
      addToast({
        type: 'success',
        title: 'Authenticated',
        message: 'Staff officer authenticated successfully. Token saved.'
      });
    } else {
      addToast({
        type: 'error',
        title: 'Authentication Failed',
        message: res.error || 'Invalid official credentials.'
      });
    }
  };

  // Process genuine inference response from FastAPI
  const processInferenceResponse = (
    res: { success: boolean; data?: DetectionAnalysisResult; error?: string; errorCode?: string; details?: any[] },
    snapshotUrl: string,
    sourceLabel: string
  ) => {
    if (!res.success) {
      setErrorMessage(res.error || 'Inference analysis failed.');
      setErrorDetails(res.details || []);

      if (res.errorCode === 'UNAUTHORIZED') {
        setShowAuthModal(true);
        addToast({
          type: 'warning',
          title: 'Authentication Required',
          message: 'Officer Bearer token required to invoke POST /api/v1/detections/analyze.'
        });
      } else if (res.errorCode === 'MODEL_NOT_AVAILABLE') {
        addToast({
          type: 'error',
          title: 'Model Not Available',
          message: res.error || 'AI model weights or Roboflow API key missing.'
        });
      } else if (res.errorCode === 'REMOTE_INFERENCE_ERROR' || res.errorCode?.startsWith('ROBOFLOW_')) {
        addToast({
          type: 'error',
          title: 'Roboflow Error',
          message: res.error || 'Remote Roboflow detection service failed.'
        });
      } else {
        addToast({
          type: 'error',
          title: 'Inference Error',
          message: res.error || 'An error occurred during frame processing.'
        });
      }
      return;
    }

    const det = res.data;
    if (!det) return;

    // Map boxes to UI format
    const uiBoxes: BoundingBox[] = (det.boxes || []).map(b => ({
      id: b.id,
      label: b.label as any,
      confidence: b.confidence,
      x: b.percentage.x,
      y: b.percentage.y,
      width: b.percentage.width,
      height: b.percentage.height,
      color: b.color || '#2563EB'
    }));

    setOverlayBoxes(uiBoxes);

    // Determine status badge
    let outcome: 'HELMET_DETECTED' | 'NO_HELMET_CANDIDATE' | 'UNCERTAIN' | 'NO_DETECTION' | 'COCO_OBJECTS_ONLY';
    if (det.isCandidateViolation) {
      outcome = 'NO_HELMET_CANDIDATE';
    } else if (det.helmetClassificationAvailable && det.boxes.some(b => b.category === 'HELMET_COMPLIANT')) {
      outcome = 'HELMET_DETECTED';
    } else if (!det.helmetClassificationAvailable && det.totalDetections > 0) {
      outcome = 'COCO_OBJECTS_ONLY';
    } else {
      outcome = 'NO_DETECTION';
    }

    const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const nowIso = new Date().toISOString().replace('T', ' ').substring(0, 19);

    // If candidate violation, ingest to reviewer queue
    if (det.isCandidateViolation && det.caseId) {
      const candidateCase: ViolationCase = {
        id: det.caseId,
        timestamp: nowIso,
        camera: {
          id: selectedDeviceId || 'CAM-OPERATOR-WEBCAM',
          name: sourceLabel,
          location: 'Operator Workspace Live Camera',
          type: selectedSourceType
        },
        violationType: det.violationType || 'NO_HELMET_RIDER',
        confidence: det.violationConfidence || 0.85,
        status: 'PENDING_REVIEW',
        evidenceImageUrl: snapshotUrl,
        evidenceQuality: 'HIGH',
        boundingBoxes: uiBoxes,
        linkedPerson: undefined,
        reviewerNotes: '',
        reviewHistory: [
          {
            id: `audit-${Date.now()}`,
            timestamp: nowIso,
            actor: currentUser?.name || 'Camera Operator',
            role: 'operator',
            action: 'CREATED',
            notes: `Candidate frame analyzed via live YOLO. Detected: ${det.violationType}. Queued with status PENDING_REVIEW.`
          }
        ]
      };
      addNewCapturedCase(candidateCase);
    }

    setRecentCaptures(prev => [
      {
        id: det.caseId || `DET-${Date.now().toString().slice(-4)}`,
        url: snapshotUrl,
        time: nowTime,
        outcome: outcome
      },
      ...prev.slice(0, 5)
    ]);

    setLastDetectionResult({
      status: outcome,
      confidence: det.violationConfidence || (det.boxes[0]?.confidence ?? 0.0),
      violationType: det.violationType || undefined,
      caseId: det.caseId || undefined,
      savedToQueue: det.isCandidateViolation,
      totalDetections: det.totalDetections,
      vehiclesCount: det.vehicles?.length || 0,
      personsCount: det.persons?.length || 0,
      processingTimeMs: det.processingTimeMs,
      helmetClassificationAvailable: det.helmetClassificationAvailable,
      helmetClassificationMessage: det.helmetClassificationMessage,
      boxes: uiBoxes
    });

    addToast({
      type: det.isCandidateViolation ? 'warning' : 'success',
      title: 'Frame Analyzed',
      message: `Processed in ${det.processingTimeMs}ms. ${det.totalDetections} object(s) detected.`
    });
  };

  // Capture frame from webcam and submit to POST /api/v1/detections/analyze
  const handleCaptureFrame = async () => {
    if (!videoRef.current || !isStreaming) {
      setErrorMessage('Please start the camera before capturing a live frame.');
      return;
    }

    setIsCapturing(true);
    setErrorMessage(null);
    setErrorDetails([]);

    try {
      const snapshotUrl = cameraService.captureFrame(videoRef.current);
      setCapturedSnapshotUrl(snapshotUrl);

      const blob = await cameraService.captureFrameBlob(videoRef.current);

      const sourceLabel = selectedSourceType === 'WEBCAM' 
        ? 'Laptop Operator Webcam' 
        : selectedSourceType === 'IP_CAMERA' 
          ? 'MG Road IP Cam 01' 
          : 'Koramangala CCTV Stream';

      const res = await cameraService.analyzeFrame(blob, selectedDeviceId, sourceLabel);
      processInferenceResponse(res, snapshotUrl, sourceLabel);
    } catch (err: any) {
      setErrorMessage('Failed to capture or dispatch frame: ' + err.message);
    } finally {
      setIsCapturing(false);
    }
  };

  // Handle uploaded image file directly
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsCapturing(true);
    setErrorMessage(null);
    setErrorDetails([]);

    const reader = new FileReader();
    reader.onload = async () => {
      const snapshotUrl = reader.result as string;
      setCapturedSnapshotUrl(snapshotUrl);

      try {
        const sourceLabel = `File Upload: ${file.name}`;
        const res = await cameraService.analyzeFrame(file, selectedDeviceId, sourceLabel);
        processInferenceResponse(res, snapshotUrl, sourceLabel);
      } catch (err: any) {
        setErrorMessage('Failed to analyze uploaded file: ' + err.message);
      } finally {
        setIsCapturing(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.onerror = () => {
      setErrorMessage('Failed to read image file.');
      setIsCapturing(false);
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="space-y-5">
      {/* Top Banner Notice */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Radio className="w-5 h-5 text-emerald-600 animate-pulse" />
            Live Surveillance Feed &amp; YOLO Edge Inference Workstation
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real FastAPI endpoint (<code className="bg-slate-100 px-1 py-0.5 rounded font-mono text-[11px]">POST /api/v1/detections/analyze</code>) with CPU inference.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {/* JWT Auth Status Badge */}
          <button
            type="button"
            onClick={() => setShowAuthModal(true)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full font-medium border transition-colors ${
              authToken 
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100' 
                : 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100'
            }`}
            title="Click to configure JWT authentication token"
          >
            <Key className="w-3.5 h-3.5" />
            <span>JWT: {authToken ? 'Authorized' : 'Authenticate'}</span>
          </button>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-medium border border-slate-200">
            <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-emerald-500' : 'bg-slate-400'}`} />
            <span>Feed: {isStreaming ? 'STREAMING ACTIVE' : 'STANDBY'}</span>
          </div>

          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full font-medium border ${
            modelStatus?.isLoaded 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}>
            <Sparkles className="w-3.5 h-3.5" />
            <span>
              Model: {modelStatus?.isLoaded 
                ? (modelStatus.provider === 'roboflow' ? 'Roboflow Hosted' : 'Loaded (CPU)') 
                : 'Not Ready'}
            </span>
          </div>
        </div>
      </div>

      {/* Model Status Alert Banner when Weights/API Key are Absent */}
      {modelStatus && !modelStatus.isLoaded && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 text-xs text-amber-900 flex items-start gap-3 shadow-xs">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-bold text-amber-950">
              {modelStatus.provider === 'roboflow' 
                ? 'Roboflow API Key Not Configured (MODEL_NOT_AVAILABLE)' 
                : 'AI Model Weights Unavailable (MODEL_NOT_AVAILABLE)'}
            </div>
            <p className="text-amber-800 leading-relaxed">
              {modelStatus.provider === 'roboflow' ? (
                <>
                  Roboflow API key is not configured. Please set <code className="font-mono font-semibold bg-amber-100 px-1 py-0.5 rounded">ROBOFLOW_API_KEY</code> in <code className="font-mono bg-amber-100 px-1 py-0.5 rounded">backend/.env</code> to enable hosted helmet detection ({modelStatus.modelId || 'helmet-and-no-helmet-rider-detection/6'}).
                </>
              ) : (
                <>
                  Trained computer vision weights are not present at <code className="font-mono font-semibold bg-amber-100 px-1 py-0.5 rounded">models/yolov8n-traffic.pt</code>.
                  TrafficGuard strictly prevents simulated or hardcoded detections in production. Please place trained weights into the <code className="font-mono">models/</code> directory.
                </>
              )}
            </p>
          </div>
        </div>
      )}

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
              className={`w-full h-full object-cover ${isStreaming && !capturedSnapshotUrl ? 'block' : 'hidden'}`}
            />

            {/* Captured Snapshot Preview when frame is analyzed */}
            {capturedSnapshotUrl && (
              <div className="relative w-full h-full flex items-center justify-center">
                <img
                  src={capturedSnapshotUrl}
                  alt="Captured frame"
                  className="w-full h-full object-cover"
                />

                {/* Genuine YOLO Bounding Box Overlays */}
                {showOverlay && overlayBoxes.map(box => {
                  const isViolation = box.label === 'NO_HELMET' || box.label === 'WITHOUT_HELMET' || box.color === '#DC2626';
                  return (
                    <div
                      key={box.id}
                      style={{
                        left: `${box.x}%`,
                        top: `${box.y}%`,
                        width: `${box.width}%`,
                        height: `${box.height}%`,
                        borderColor: box.color || (isViolation ? '#DC2626' : '#2563EB'),
                      }}
                      className="absolute border-2 transition-all pointer-events-none"
                    >
                      <div
                        className="absolute -top-5 left-0 px-1 py-0.5 rounded text-[9px] font-bold tracking-tight text-white whitespace-nowrap shadow-xs flex items-center gap-1"
                        style={{ backgroundColor: box.color || (isViolation ? '#DC2626' : '#2563EB') }}
                      >
                        <span>{box.label.replace('_', ' ')}</span>
                        <span>{(box.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  );
                })}

                {/* Reset to live video button */}
                {isStreaming && (
                  <button
                    type="button"
                    onClick={() => {
                      setCapturedSnapshotUrl(null);
                      setOverlayBoxes([]);
                    }}
                    className="absolute top-3 right-3 px-2 py-1 rounded bg-black/75 hover:bg-black text-white text-[11px] font-semibold border border-white/20 transition-colors"
                  >
                    Resume Live Stream
                  </button>
                )}
              </div>
            )}

            {/* Standby Neutral Placeholder when camera is off and no snapshot */}
            {!isStreaming && !capturedSnapshotUrl && (
              <div className="text-center p-8 max-w-sm">
                <div className="w-14 h-14 rounded-full bg-slate-800 text-slate-400 mx-auto flex items-center justify-center mb-3">
                  <Camera className="w-7 h-7" />
                </div>
                <h4 className="text-sm font-bold text-slate-200">
                  {selectedSourceType === 'WEBCAM' ? 'Webcam in Standby' : 'Network Stream Standby'}
                </h4>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Start your local webcam to capture live frames, or upload an image file below to test the genuine YOLO inference engine.
                </p>
                <div className="mt-4 flex items-center justify-center gap-2">
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
              <div className="absolute inset-x-4 bottom-4 p-3 bg-red-950/95 border border-red-500/60 rounded-lg text-white text-xs flex flex-col gap-1.5 backdrop-blur-xs z-20">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div className="flex-1 font-semibold">{errorMessage}</div>
                </div>
                {errorDetails.length > 0 && (
                  <div className="pl-6 space-y-0.5 text-[11px] text-red-200">
                    {errorDetails.map((d, i) => (
                      <div key={i}>• {d.message}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Live Camera HUD Indicators */}
            {isStreaming && !capturedSnapshotUrl && (
              <div className="absolute top-3 left-3 flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-black/70 text-emerald-400 font-mono text-[11px] font-bold border border-emerald-500/40">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  REC LIVE
                </span>
                <span className="px-2 py-0.5 rounded bg-black/70 text-white font-mono text-[11px] border border-white/20">
                  30 FPS • 720p
                </span>
              </div>
            )}
          </div>

          {/* Capture & Upload Trigger Bar */}
          <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileUpload}
                className="hidden"
                id="image-file-input"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isCapturing}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg transition-colors shadow-xs disabled:opacity-50"
              >
                <Upload className="w-3.5 h-3.5 text-slate-500" />
                <span>Upload Image File</span>
              </button>

              {overlayBoxes.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowOverlay(!showOverlay)}
                  className="inline-flex items-center gap-1 px-2.5 py-2 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>{showOverlay ? 'Boxes Visible' : 'Boxes Hidden'}</span>
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={handleCaptureFrame}
              disabled={isCapturing || !isStreaming}
              className="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-all flex items-center gap-2 shadow-xs disabled:opacity-50"
            >
              <Camera className="w-4 h-4" />
              <span>{isCapturing ? 'Running YOLO Inference...' : 'Capture & Analyze Frame'}</span>
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
              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                {modelStatus?.provider === 'roboflow' ? 'ROBOFLOW HOSTED INFERENCE' : 'GENUINE YOLO INFERENCE'}
              </span>
            </div>

            {lastDetectionResult ? (
              <div className="space-y-3">
                <div className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 ${
                  lastDetectionResult.status === 'NO_HELMET_CANDIDATE' 
                    ? 'bg-rose-50 border-rose-200' 
                    : lastDetectionResult.status === 'HELMET_DETECTED'
                      ? 'bg-emerald-50 border-emerald-200'
                      : 'bg-slate-50 border-slate-200'
                }`}>
                  <div>
                    <span className="text-[11px] text-slate-500 block font-medium">Outcome Classification:</span>
                    <div className="text-sm font-bold text-slate-900 mt-0.5">
                      {lastDetectionResult.status.replace(/_/g, ' ')}
                    </div>
                    {lastDetectionResult.violationType && (
                      <span className="inline-block mt-1 text-[11px] font-semibold text-rose-700 bg-rose-100 px-1.5 py-0.5 rounded">
                        {lastDetectionResult.violationType}
                      </span>
                    )}
                  </div>

                  <div className="text-right">
                    <span className="text-[11px] text-slate-500 block font-medium">Confidence:</span>
                    <span className={`text-base font-bold ${
                      lastDetectionResult.confidence >= 0.85 ? 'text-emerald-700' : 'text-amber-700'
                    }`}>
                      {(lastDetectionResult.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Helmet status note */}
                <div className="text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700">
                  <div className="font-semibold text-[11px] text-slate-800">Capability Assessment:</div>
                  <div className="text-[11px] mt-0.5 leading-relaxed">
                    {lastDetectionResult.helmetClassificationMessage}
                  </div>
                </div>

                <div className="text-xs space-y-1.5 text-slate-600 pt-1">
                  <div className="flex justify-between">
                    <span>Detected Objects:</span>
                    <span className="font-semibold text-slate-800">
                      {lastDetectionResult.totalDetections} total ({lastDetectionResult.vehiclesCount} vehicle, {lastDetectionResult.personsCount} person)
                    </span>
                  </div>
                  {lastDetectionResult.caseId && (
                    <div className="flex justify-between">
                      <span>Candidate Draft Case ID:</span>
                      <span className="font-mono font-bold text-slate-900">{lastDetectionResult.caseId}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>Reviewer Queue Ingestion:</span>
                    {lastDetectionResult.savedToQueue ? (
                      <span className="text-emerald-700 font-semibold flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Queued (PENDING_REVIEW)
                      </span>
                    ) : (
                      <span className="text-slate-400 font-medium">
                        Not flagged (No sanction draft needed)
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <HelpCircle className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                <span>No frame analyzed yet. Capture a live webcam frame or upload an image file to run genuine AI inference.</span>
              </div>
            )}

            {/* Model & Hardware Telemetry strip */}
            <div className="p-3 rounded-lg bg-slate-50/80 border border-slate-200 text-xs space-y-1 text-slate-500">
              <div className="flex justify-between">
                <span>Model Architecture:</span>
                <span className="font-medium text-slate-800">
                  {modelStatus?.provider === 'roboflow' 
                    ? `Roboflow: ${modelStatus.modelId || 'helmet-and-no-helmet-rider-detection/6'}`
                    : 'YOLOv8n-Traffic (CPU)'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Inference Latency:</span>
                <span className="font-mono text-slate-800">
                  {lastDetectionResult ? `${lastDetectionResult.processingTimeMs} ms` : '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Helmet Classes:</span>
                <span className={`font-medium ${
                  modelStatus?.helmetClassificationSupported ? 'text-emerald-700' : 'text-amber-700'
                }`}>
                  {modelStatus?.helmetClassificationSupported ? 'Supported' : 'Unavailable (Generic Weights)'}
                </span>
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

      {/* Staff Authentication Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">Staff JWT Authorization</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAuthModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold p-1"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              FastAPI endpoint <code className="bg-slate-100 px-1 py-0.5 rounded font-mono text-[11px]">POST /api/v1/detections/analyze</code> requires an authenticated officer JWT token.
            </p>

            <form onSubmit={handleLoginSubmit} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">Official Email</label>
                <input
                  type="email"
                  value={authEmail}
                  onChange={e => setAuthEmail(e.target.value)}
                  placeholder="admin@trafficguard.gov.in"
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">Password</label>
                <input
                  type="password"
                  value={authPassword}
                  onChange={e => setAuthPassword(e.target.value)}
                  placeholder="Enter officer password"
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="pt-1">
                <label className="text-[11px] font-medium text-slate-500 block mb-1">
                  Or paste existing Bearer Token directly:
                </label>
                <input
                  type="text"
                  value={authManualToken}
                  onChange={e => setAuthManualToken(e.target.value)}
                  placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6..."
                  className="w-full text-xs font-mono px-3 py-2 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAuthModal(false)}
                  className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoggingIn}
                  className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 shadow-xs"
                >
                  {isLoggingIn ? 'Authenticating...' : 'Authenticate & Save Token'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
