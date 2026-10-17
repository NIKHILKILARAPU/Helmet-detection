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
  Layers,
  Clock,
  RefreshCw
} from 'lucide-react';
import { useApp } from '../../context';
import { cameraService } from '../../services/cameraService';
import { apiClient } from '../../services/api';
import type { CameraDevice } from '../../services/cameraService';
import type { BoundingBox, ViolationCase, DetectionAnalysisResult, RiderDetection, PlateMatchResult } from '../../types';
import { EvidenceCropImage } from '../../components/common/EvidenceCropImage';

export const CameraOperatorPage: React.FC = () => {
  const { addNewCapturedCase, addToast, currentUser } = useApp();

  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Streaming & Hardware state
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [availableDevices, setAvailableDevices] = useState<CameraDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('default');
  const [selectedSourceType, setSelectedSourceType] = useState<'WEBCAM' | 'IP_CAMERA' | 'CCTV_STREAM'>('WEBCAM');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<any[]>([]);

  // Automatic Periodic Capture & Monitoring State
  const [isMonitoring, setIsMonitoring] = useState<boolean>(false);
  const [captureInterval, setCaptureInterval] = useState<number>(3); // seconds
  const [cooldownSeconds, setCooldownSeconds] = useState<number>(15); // seconds
  const [processedFramesCount, setProcessedFramesCount] = useState<number>(0);
  const [lastCaptureTime, setLastCaptureTime] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<'IDLE' | 'MONITORING' | 'CAPTURING' | 'ANALYZING' | 'COOLDOWN' | 'ERROR'>('IDLE');

  // Preview & Overlay State
  const [activeView, setActiveView] = useState<'LIVE' | 'SNAPSHOT'>('LIVE');
  const [capturedSnapshotUrl, setCapturedSnapshotUrl] = useState<string | null>(null);
  const [overlayBoxes, setOverlayBoxes] = useState<BoundingBox[]>([]);
  const [showOverlay, setShowOverlay] = useState<boolean>(true);
  const [isManualCapturing, setIsManualCapturing] = useState<boolean>(false);

  // Refs for timer management & re-entrancy protection
  const isMonitoringRef = useRef<boolean>(false);
  const isAnalyzingRef = useRef<boolean>(false);
  const timerRef = useRef<any>(null);
  const captureIntervalRef = useRef<number>(3);
  const cooldownSecondsRef = useRef<number>(15);

  // Sync refs with state values
  useEffect(() => {
    captureIntervalRef.current = captureInterval;
  }, [captureInterval]);

  useEffect(() => {
    cooldownSecondsRef.current = cooldownSeconds;
  }, [cooldownSeconds]);

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

  const [recentCaptures, setRecentCaptures] = useState<{ id: string; url: string; time: string; outcome: string; isDeduplicated?: boolean }[]>([]);
  const [lastDetectionResult, setLastDetectionResult] = useState<{
    status: 'HELMET_DETECTED' | 'NO_HELMET_CANDIDATE' | 'UNCERTAIN' | 'NO_DETECTION' | 'COCO_OBJECTS_ONLY';
    confidence: number;
    violationType?: string;
    caseId?: string;
    savedToQueue: boolean;
    isDeduplicated?: boolean;
    cooldownSecondsRemaining?: number | null;
    totalDetections: number;
    vehiclesCount: number;
    personsCount: number;
    processingTimeMs: number;
    helmetClassificationAvailable: boolean;
    helmetClassificationMessage: string;
    boxes: BoundingBox[];
    riders?: RiderDetection[];
    plateMatch?: PlateMatchResult | null;
  } | null>(null);

  // Fetch model status
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

  // Handle stream termination (e.g., unplugged webcam or browser revocation)
  const handleStreamEnded = useCallback(() => {
    isMonitoringRef.current = false;
    setIsMonitoring(false);
    setAnalysisStatus('IDLE');
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
    setErrorMessage('Camera hardware stream was terminated or disconnected.');
    addToast({
      type: 'error',
      title: 'Camera Disconnected',
      message: 'Video hardware stream was ended. Monitoring has been halted.'
    });
  }, [addToast]);

  // Load available media devices and model status
  useEffect(() => {
    cameraService.getAvailableVideoDevices().then(devices => {
      setAvailableDevices(devices);
      if (devices.length > 0) {
        setSelectedDeviceId(devices[0].deviceId);
      }
    });

    checkModelStatus();

    // Cleanup camera stream and periodic timer on unmount
    return () => {
      isMonitoringRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      cameraService.stopWebcam();
    };
  }, [checkModelStatus]);

  // Process genuine inference response from FastAPI
  const processInferenceResponse = useCallback((
    res: { success: boolean; data?: DetectionAnalysisResult; error?: string; errorCode?: string; details?: any[] },
    snapshotUrl: string,
    sourceLabel: string
  ) => {
    if (!res.success) {
      setErrorMessage(res.error || 'Inference analysis failed.');
      setErrorDetails(res.details || []);

      if (res.errorCode === 'UNAUTHORIZED') {
        if (isMonitoringRef.current) {
          isMonitoringRef.current = false;
          setIsMonitoring(false);
          if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
          }
        }
        setAuthTokenState(null);
        setShowAuthModal(true);
        addToast({
          type: 'warning',
          title: 'Session Expired or Unauthorized',
          message: res.error || 'Officer Bearer token required or session expired. Please log in again.'
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
      } else if (res.errorCode === 'NETWORK_ERROR') {
        addToast({
          type: 'error',
          title: 'Backend Connection Failed',
          message: res.error || 'Unable to connect to FastAPI backend at http://127.0.0.1:8000.'
        });
      }
      return;
    }

    const det = res.data;
    if (!det) return;

    // Map boxes to UI format with real labels
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

    // If candidate violation AND NOT deduplicated, ingest to reviewer queue
    if (det.isCandidateViolation && det.caseId && !det.isDeduplicated) {
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
            notes: `Candidate frame analyzed via Roboflow Hosted Inference. Detected: ${det.violationType}. Queued with status PENDING_REVIEW.`
          }
        ],
        riders: det.riders,
        plateMatch: det.plateMatch
      };
      addNewCapturedCase(candidateCase);
    }

    setRecentCaptures(prev => [
      {
        id: det.caseId || `DET-${Date.now().toString().slice(-4)}`,
        url: snapshotUrl,
        time: nowTime,
        outcome: outcome,
        isDeduplicated: det.isDeduplicated
      },
      ...prev.slice(0, 5)
    ]);

    setLastDetectionResult({
      status: outcome,
      confidence: det.violationConfidence || (det.boxes[0]?.confidence ?? 0.0),
      violationType: det.violationType || undefined,
      caseId: det.caseId || undefined,
      savedToQueue: det.isCandidateViolation && !det.isDeduplicated,
      isDeduplicated: det.isDeduplicated,
      cooldownSecondsRemaining: det.cooldownSecondsRemaining,
      totalDetections: det.totalDetections,
      vehiclesCount: det.vehicles?.length || 0,
      personsCount: det.persons?.length || 0,
      processingTimeMs: det.processingTimeMs,
      helmetClassificationAvailable: det.helmetClassificationAvailable,
      helmetClassificationMessage: det.helmetClassificationMessage,
      boxes: uiBoxes,
      riders: det.riders,
      plateMatch: det.plateMatch
    });
  }, [addNewCapturedCase, addToast, currentUser?.name, selectedDeviceId, selectedSourceType]);

  // Execute a single cycle of frame capture and analysis (mutex guarded)
  const executeCaptureCycle = useCallback(async (): Promise<void> => {
    if (isAnalyzingRef.current) {
      return; // Prevent overlapping requests
    }
    if (!videoRef.current || !cameraService.isStreaming()) {
      return;
    }

    isAnalyzingRef.current = true;
    setAnalysisStatus('CAPTURING');

    try {
      const snapshotUrl = cameraService.captureFrame(videoRef.current);
      setCapturedSnapshotUrl(snapshotUrl);
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLastCaptureTime(timeStr);

      setAnalysisStatus('ANALYZING');
      const blob = await cameraService.captureFrameBlob(videoRef.current);

      const sourceLabel = selectedSourceType === 'WEBCAM' 
        ? 'Laptop Operator Live Webcam' 
        : selectedSourceType === 'IP_CAMERA' 
          ? 'MG Road IP Cam 01' 
          : 'CCTV Traffic Cam 02';
      // Only send camera_id if it is a valid 24-character hexadecimal MongoDB ObjectId
      const validCameraId = /^[0-9a-fA-F]{24}$/.test(selectedDeviceId) ? selectedDeviceId : undefined;

      const res = await cameraService.analyzeFrame(
        blob,
        validCameraId,
        sourceLabel,
        cooldownSecondsRef.current
      );

      setProcessedFramesCount(prev => prev + 1);

      if (res.success && res.data) {
        processInferenceResponse(res, snapshotUrl, sourceLabel);
        if (res.data.isDeduplicated) {
          setAnalysisStatus('COOLDOWN');
        } else {
          setAnalysisStatus('MONITORING');
        }
      } else {
        // Non-fatal error during monitoring loop: record failure but allow loop to continue
        setAnalysisStatus('ERROR');
        processInferenceResponse(res, snapshotUrl, sourceLabel);
      }
    } catch (err: any) {
      // Non-fatal capture or network glitch
      setAnalysisStatus('ERROR');
      setErrorMessage(err.message || 'Frame capture/analysis encountered an issue.');
    } finally {
      isAnalyzingRef.current = false;
    }
  }, [processInferenceResponse, selectedDeviceId, selectedSourceType]);

  // Self-scheduling timer loop ensuring zero request overlap without circular reference
  const scheduleNextCaptureRef = useRef<() => void>(() => {});
  const scheduleNextCapture = useCallback(() => {
    if (!isMonitoringRef.current) return;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    const intervalMs = Math.max(1000, captureIntervalRef.current * 1000);
    timerRef.current = setTimeout(async () => {
      if (!isMonitoringRef.current) return;
      await executeCaptureCycle();
      if (isMonitoringRef.current) {
        scheduleNextCaptureRef.current();
      }
    }, intervalMs);
  }, [executeCaptureCycle]);

  useEffect(() => {
    scheduleNextCaptureRef.current = scheduleNextCapture;
  }, [scheduleNextCapture]);

  // Start continuous automatic monitoring
  const handleStartMonitoring = async () => {
    setErrorMessage(null);
    setErrorDetails([]);

    // 1. Validate source mode (Webcam required for browser canvas frame capture)
    if (selectedSourceType !== 'WEBCAM') {
      const msg = 'Automated periodic camera capture operates on local workstation hardware (Integrated Webcam). External IP camera / CCTV feeds require network stream capture agents. Please switch Source to "Integrated Webcam" or use "Upload Image File" for network surveillance frames.';
      setErrorMessage(msg);
      addToast({
        type: 'warning',
        title: 'Local Webcam Required',
        message: 'Switch Source to "Integrated Webcam" for live periodic monitoring.'
      });
      return;
    }

    // 2. Validate authentication token before launching capture loop
    if (!apiClient.getAuthToken()) {
      setShowAuthModal(true);
      const msg = 'Staff authentication token required. Please authenticate with officer credentials to invoke POST /api/v1/detections/analyze.';
      setErrorMessage(msg);
      addToast({
        type: 'warning',
        title: 'Authentication Required',
        message: msg
      });
      return;
    }

    if (!videoRef.current) return;

    try {
      // If camera hardware not yet streaming, initialize it first
      if (!cameraService.isStreaming()) {
        await cameraService.startWebcam(videoRef.current, selectedDeviceId, handleStreamEnded);
        setIsStreaming(true);
      }

      isMonitoringRef.current = true;
      setIsMonitoring(true);
      setAnalysisStatus('MONITORING');

      addToast({
        type: 'success',
        title: 'Periodic Monitoring Active',
        message: `Automatic capture started (Interval: ${captureInterval}s, Cooldown: ${cooldownSeconds}s).`
      });

      // Run initial capture cycle immediately
      await executeCaptureCycle();

      // Schedule subsequent cycles
      if (isMonitoringRef.current) {
        scheduleNextCapture();
      }
    } catch (err: any) {
      isMonitoringRef.current = false;
      setIsMonitoring(false);
      setIsStreaming(false);
      setAnalysisStatus('ERROR');

      let msg = 'Failed to access camera device.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Camera permission was denied. Please allow camera permissions in your browser.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No video capture hardware was detected on your machine.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        msg = 'Camera is already in use by another application.';
      } else if (err.message) {
        msg = err.message;
      }
      setErrorMessage(msg);
      addToast({
        type: 'error',
        title: 'Camera Access Error',
        message: msg
      });
    }
  };

  // Stop continuous automatic monitoring
  const handleStopMonitoring = useCallback(() => {
    isMonitoringRef.current = false;
    setIsMonitoring(false);
    setAnalysisStatus('IDLE');

    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    cameraService.stopWebcam();
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);

    addToast({
      type: 'info',
      title: 'Monitoring Stopped',
      message: 'Automatic camera capture and monitoring loop halted. Hardware released.'
    });
  }, [addToast]);

  // Standalone single camera start (view only)
  const handleStartCamera = async () => {
    setErrorMessage(null);
    setErrorDetails([]);
    if (!videoRef.current) return;

    try {
      await cameraService.startWebcam(videoRef.current, selectedDeviceId, handleStreamEnded);
      setIsStreaming(true);
      addToast({
        type: 'success',
        title: 'Camera Initialized',
        message: 'Webcam feed active. You can now Start Monitoring or capture ad-hoc frames.'
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
      } else if (err.message) {
        msg = err.message;
      }
      setErrorMessage(msg);
      addToast({
        type: 'error',
        title: 'Camera Access Error',
        message: msg
      });
    }
  };

  // Standalone camera stop
  const handleStopCamera = useCallback(() => {
    if (isMonitoring) {
      handleStopMonitoring();
      return;
    }
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
  }, [handleStopMonitoring, isMonitoring, addToast]);

  // Manual single frame capture (ad-hoc)
  const handleManualCaptureFrame = async () => {
    if (!videoRef.current || !isStreaming) {
      setErrorMessage('Please start the camera before capturing a live frame.');
      return;
    }

    if (!apiClient.getAuthToken()) {
      setShowAuthModal(true);
      const msg = 'Staff authentication token required. Please log in with official credentials to capture and analyze frames.';
      setErrorMessage(msg);
      addToast({
        type: 'warning',
        title: 'Authentication Required',
        message: msg
      });
      return;
    }

    setIsManualCapturing(true);
    setErrorMessage(null);
    setErrorDetails([]);

    try {
      const snapshotUrl = cameraService.captureFrame(videoRef.current);
      setCapturedSnapshotUrl(snapshotUrl);
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLastCaptureTime(timeStr);

      const blob = await cameraService.captureFrameBlob(videoRef.current);

      const sourceLabel = selectedSourceType === 'WEBCAM' 
        ? 'Laptop Operator Webcam (Manual)' 
        : selectedSourceType === 'IP_CAMERA' 
          ? 'MG Road IP Cam 01' 
          : 'Koramangala CCTV Stream';

      const res = await cameraService.analyzeFrame(blob, selectedDeviceId, sourceLabel, cooldownSecondsRef.current);
      setProcessedFramesCount(prev => prev + 1);
      processInferenceResponse(res, snapshotUrl, sourceLabel);
    } catch (err: any) {
      setErrorMessage('Failed to capture or dispatch frame: ' + err.message);
    } finally {
      setIsManualCapturing(false);
    }
  };

  // Handle uploaded image file directly
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!apiClient.getAuthToken()) {
      setShowAuthModal(true);
      const msg = 'Staff authentication token required. Please log in with official credentials to analyze surveillance images.';
      setErrorMessage(msg);
      addToast({
        type: 'warning',
        title: 'Authentication Required',
        message: msg
      });
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setIsManualCapturing(true);
    setErrorMessage(null);
    setErrorDetails([]);

    const reader = new FileReader();
    reader.onload = async () => {
      const snapshotUrl = reader.result as string;
      setCapturedSnapshotUrl(snapshotUrl);
      setActiveView('SNAPSHOT');
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLastCaptureTime(timeStr);

      try {
        const sourceLabel = `File Upload: ${file.name}`;
        const res = await cameraService.analyzeFrame(file, selectedDeviceId, sourceLabel, cooldownSecondsRef.current);
        setProcessedFramesCount(prev => prev + 1);
        processInferenceResponse(res, snapshotUrl, sourceLabel);
      } catch (err: any) {
        setErrorMessage('Failed to analyze uploaded file: ' + err.message);
      } finally {
        setIsManualCapturing(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.onerror = () => {
      setErrorMessage('Failed to read image file.');
      setIsManualCapturing(false);
    };
    reader.readAsDataURL(file);
  };

  // Handle login for JWT auth
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
        message: `Staff officer authenticated successfully (${res.tokenType || 'bearer'}).`
      });
    } else {
      addToast({
        type: 'error',
        title: 'Authentication Failed',
        message: res.error || 'Invalid official credentials.'
      });
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Banner Notice */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Radio className={`w-5 h-5 ${isMonitoring ? 'text-rose-600 animate-pulse' : 'text-emerald-600'}`} />
            Live Surveillance &amp; Periodic Camera Monitoring Workstation
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Automated periodic frame capture with Roboflow Hosted Inference (<code className="bg-slate-100 px-1 py-0.5 rounded font-mono text-[11px]">POST /api/v1/detections/analyze</code>).
          </p>
        </div>

        <div className="flex items-center gap-2.5 text-xs flex-wrap">
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

          {/* Monitoring State Badge */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full font-medium border ${
            isMonitoring
              ? 'bg-rose-50 text-rose-700 border-rose-300 animate-pulse'
              : 'bg-slate-100 text-slate-700 border-slate-200'
          }`}>
            <span className={`w-2 h-2 rounded-full ${isMonitoring ? 'bg-rose-500' : 'bg-slate-400'}`} />
            <span>Monitoring: {isMonitoring ? `ACTIVE (${captureInterval}s)` : 'STOPPED'}</span>
          </div>

          {/* Video Stream State Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-medium border border-slate-200">
            <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-emerald-500' : 'bg-slate-400'}`} />
            <span>Feed: {isStreaming ? 'STREAMING' : 'STANDBY'}</span>
          </div>

          {/* Model Status Badge */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full font-medium border ${
            modelStatus?.isLoaded 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}>
            <Sparkles className="w-3.5 h-3.5" />
            <span>
              Model: {modelStatus?.isLoaded 
                ? (modelStatus.provider === 'roboflow' ? 'Roboflow Hosted' : 'Loaded') 
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
          <div className="p-3.5 border-b border-slate-200 bg-slate-50/80 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-1.5">
                <label className="text-xs font-semibold text-slate-700">Source:</label>
                <select
                  value={selectedSourceType}
                  onChange={e => {
                    if (isStreaming || isMonitoring) handleStopMonitoring();
                    setSelectedSourceType(e.target.value as any);
                  }}
                  className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 font-medium focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                >
                  <option value="WEBCAM">Integrated Webcam</option>
                  <option value="IP_CAMERA">IP Camera (MG Road Jn)</option>
                  <option value="CCTV_STREAM">CCTV (Koramangala 80ft)</option>
                </select>
              </div>

              {selectedSourceType === 'WEBCAM' && availableDevices.length > 1 && (
                <select
                  value={selectedDeviceId}
                  onChange={e => setSelectedDeviceId(e.target.value)}
                  disabled={isStreaming || isMonitoring}
                  className="text-xs px-2 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 disabled:opacity-50"
                >
                  {availableDevices.map(d => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label}</option>
                  ))}
                </select>
              )}

              {/* Configurable Periodic Interval */}
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                <label className="text-xs font-semibold text-slate-700">Interval:</label>
                <select
                  value={captureInterval}
                  onChange={e => setCaptureInterval(Number(e.target.value))}
                  disabled={isMonitoring}
                  className="text-xs px-2 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 font-medium disabled:opacity-60"
                >
                  <option value={1}>1 sec</option>
                  <option value={2}>2 sec</option>
                  <option value={3}>3 sec (Default)</option>
                  <option value={5}>5 sec</option>
                  <option value={10}>10 sec</option>
                </select>
              </div>

              {/* Configurable Deduplication Cooldown */}
              <div className="flex items-center gap-1.5">
                <label className="text-xs font-semibold text-slate-700">Cooldown:</label>
                <select
                  value={cooldownSeconds}
                  onChange={e => setCooldownSeconds(Number(e.target.value))}
                  disabled={isMonitoring}
                  className="text-xs px-2 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 font-medium disabled:opacity-60"
                >
                  <option value={5}>5 sec</option>
                  <option value={10}>10 sec</option>
                  <option value={15}>15 sec (Default)</option>
                  <option value={30}>30 sec</option>
                  <option value={60}>60 sec</option>
                </select>
              </div>
            </div>

            {/* Start / Stop Monitoring Action Buttons */}
            <div className="flex items-center gap-2">
              {!isMonitoring ? (
                <button
                  type="button"
                  onClick={handleStartMonitoring}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors shadow-xs"
                >
                  <Play className="w-3.5 h-3.5 fill-white" />
                  <span>Start Monitoring</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStopMonitoring}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg transition-colors shadow-xs animate-pulse"
                >
                  <Square className="w-3.5 h-3.5 fill-white" />
                  <span>Stop Monitoring</span>
                </button>
              )}

              {!isMonitoring && (
                !isStreaming ? (
                  <button
                    type="button"
                    onClick={handleStartCamera}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg"
                    title="Initialize camera hardware preview only"
                  >
                    <Video className="w-3.5 h-3.5 text-slate-500" />
                    <span>View Feed</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleStopCamera}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg"
                  >
                    <span>Close Feed</span>
                  </button>
                )
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
              className={`w-full h-full object-cover ${(isStreaming && activeView === 'LIVE') || (!capturedSnapshotUrl && isStreaming) ? 'block' : 'hidden'}`}
            />

            {/* Snapshot View when selected or after manual file upload */}
            {capturedSnapshotUrl && activeView === 'SNAPSHOT' && (
              <div className="relative w-full h-full flex items-center justify-center">
                <img
                  src={capturedSnapshotUrl}
                  alt="Captured frame"
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            {/* Bounding Box Overlays (rendered directly over video or snapshot) */}
            {showOverlay && (isStreaming || capturedSnapshotUrl) && overlayBoxes.map(box => {
              const isViolation = box.label === 'Without Helmet' || box.label === 'NO_HELMET' || box.label === 'WITHOUT_HELMET' || box.color === '#DC2626';
              const isHelmet = box.label === 'With Helmet' || box.label === 'HELMET' || box.label === 'WITH_HELMET';
              const isLicence = box.label === 'licence' || box.label === 'license' || box.label === 'LICENSE_PLATE';
              const borderColor = box.color || (isViolation ? '#DC2626' : isHelmet ? '#16A34A' : isLicence ? '#D97706' : '#2563EB');

              return (
                <div
                  key={box.id}
                  style={{
                    left: `${box.x}%`,
                    top: `${box.y}%`,
                    width: `${box.width}%`,
                    height: `${box.height}%`,
                    borderColor: borderColor,
                  }}
                  className="absolute border-2 transition-all pointer-events-none z-10"
                >
                  <div
                    className="absolute -top-5 left-0 px-1 py-0.5 rounded text-[9px] font-bold tracking-tight text-white whitespace-nowrap shadow-xs flex items-center gap-1"
                    style={{ backgroundColor: borderColor }}
                  >
                    <span>{box.label}</span>
                    <span>{(box.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              );
            })}

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
                  Click <strong className="text-emerald-400">Start Monitoring</strong> to activate continuous 3s periodic detection, or upload an image file below to test the genuine Roboflow inference engine.
                </p>
                <div className="mt-4 flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={handleStartMonitoring}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors shadow-xs"
                  >
                    <Play className="w-4 h-4 fill-white" />
                    <span>Start Periodic Monitoring</span>
                  </button>
                </div>
              </div>
            )}

            {/* Error Message Overlay */}
            {errorMessage && (
              <div className="absolute inset-x-4 bottom-4 p-3 bg-red-950/95 border border-red-500/60 rounded-lg text-white text-xs flex flex-col gap-1.5 backdrop-blur-xs z-20">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <div className="flex-1 font-semibold">{errorMessage}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setErrorMessage(null); setErrorDetails([]); }}
                    className="text-red-300 hover:text-white text-xs font-bold px-1"
                  >
                    ✕
                  </button>
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
            {isStreaming && (
              <div className="absolute top-3 left-3 flex items-center gap-2 z-20">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-black/70 text-emerald-400 font-mono text-[11px] font-bold border border-emerald-500/40">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  REC LIVE
                </span>
                {isMonitoring && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 font-mono text-[11px] font-bold border border-rose-500/50">
                    <RefreshCw className="w-3 h-3 animate-spin text-rose-400" />
                    PERIODIC ({captureInterval}s)
                  </span>
                )}
              </div>
            )}

            {/* Toggle View Mode (Live vs Latest Captured Snapshot) */}
            {isStreaming && capturedSnapshotUrl && (
              <div className="absolute top-3 right-3 flex items-center gap-1 z-20 bg-black/70 p-1 rounded-lg border border-white/20 text-[11px]">
                <button
                  type="button"
                  onClick={() => setActiveView('LIVE')}
                  className={`px-2 py-0.5 rounded font-medium transition-colors ${
                    activeView === 'LIVE' ? 'bg-blue-600 text-white font-bold' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Live Video
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView('SNAPSHOT')}
                  className={`px-2 py-0.5 rounded font-medium transition-colors ${
                    activeView === 'SNAPSHOT' ? 'bg-blue-600 text-white font-bold' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Latest Frame
                </button>
              </div>
            )}
          </div>

          {/* Capture & Upload Trigger Bar */}
          <div className="p-3.5 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
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
                disabled={isManualCapturing}
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

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleManualCaptureFrame}
                disabled={isManualCapturing || !isStreaming || isMonitoring}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg transition-all flex items-center gap-1.5 shadow-xs disabled:opacity-50"
                title={isMonitoring ? 'Automatic periodic capture is currently active' : 'Capture single ad-hoc frame'}
              >
                <Camera className="w-3.5 h-3.5 text-slate-600" />
                <span>{isManualCapturing ? 'Analyzing...' : 'Single Frame Snapshot'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right: AI Detection Result & Telemetry (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Automatic Monitoring Telemetry HUD Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-blue-600" />
                Continuous Monitoring Status
              </h3>
              {/* Dynamic Status Badge */}
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                analysisStatus === 'ANALYZING'
                  ? 'bg-purple-50 text-purple-700 border-purple-200 animate-pulse'
                  : analysisStatus === 'CAPTURING'
                    ? 'bg-sky-50 text-sky-700 border-sky-200'
                    : analysisStatus === 'COOLDOWN'
                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                      : analysisStatus === 'ERROR'
                        ? 'bg-rose-50 text-rose-700 border-rose-200'
                        : isMonitoring
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-100 text-slate-600 border-slate-200'
              }`}>
                {analysisStatus === 'ANALYZING' && 'ANALYZING FRAME...'}
                {analysisStatus === 'CAPTURING' && 'CAPTURING FRAME...'}
                {analysisStatus === 'COOLDOWN' && 'COOLDOWN DEDUPLICATED'}
                {analysisStatus === 'ERROR' && 'INFERENCE ERROR (RETRYING)'}
                {analysisStatus === 'MONITORING' && 'MONITORING ACTIVE'}
                {analysisStatus === 'IDLE' && 'SYSTEM STANDBY'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-[11px] text-slate-500 block">Processed Frames:</span>
                <span className="font-mono font-bold text-slate-900 text-base">{processedFramesCount}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-[11px] text-slate-500 block">Last Capture Time:</span>
                <span className="font-mono font-semibold text-slate-900 text-xs">{lastCaptureTime || 'None yet'}</span>
              </div>
            </div>

            {/* Cooldown Deduplication Alert */}
            {lastDetectionResult?.isDeduplicated && (
              <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2">
                <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-amber-950">Deduplication Cooldown Active</div>
                  <div className="text-[11px] text-amber-800 leading-relaxed mt-0.5">
                    Repeated violation on camera within the {cooldownSeconds}s cooldown window. Duplicate challan suppressed. Retaining draft case <span className="font-mono font-bold">{lastDetectionResult.caseId}</span>.
                    {lastDetectionResult.cooldownSecondsRemaining !== undefined && (
                      <span className="block mt-0.5 font-medium text-amber-900">Cooldown remaining: ~{lastDetectionResult.cooldownSecondsRemaining}s</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

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
                    <div className="text-sm font-bold text-slate-900 mt-0.5 flex items-center gap-1.5">
                      <span>{lastDetectionResult.status.replace(/_/g, ' ')}</span>
                      {lastDetectionResult.isDeduplicated && (
                        <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-semibold border border-amber-300">
                          COOLDOWN
                        </span>
                      )}
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

                {/* Capability Assessment */}
                <div className="text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700">
                  <div className="font-semibold text-[11px] text-slate-800">Capability Assessment:</div>
                  <div className="text-[11px] mt-0.5 leading-relaxed">
                    {lastDetectionResult.helmetClassificationMessage}
                  </div>
                </div>

                {/* Detected Classes Breakdown */}
                {lastDetectionResult.boxes.length > 0 && (
                  <div className="text-xs space-y-1.5">
                    <div className="font-semibold text-[11px] text-slate-700">Detections in Latest Frame:</div>
                    <div className="flex flex-wrap gap-1.5">
                      {lastDetectionResult.boxes.map((b, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded text-[11px] font-medium border text-white shadow-xs"
                          style={{ backgroundColor: b.color || '#2563EB', borderColor: b.color || '#2563EB' }}
                        >
                          {b.label}: {(b.confidence * 100).toFixed(0)}%
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Rider Evidence Crops */}
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[11px] text-slate-800 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-blue-600" />
                      Detected Rider Crops ({lastDetectionResult.riders?.length || 0})
                    </span>
                    {lastDetectionResult.riders && lastDetectionResult.riders.length > 0 && (
                      <span className="text-[10px] text-slate-500 font-medium">
                        {lastDetectionResult.riders.filter(r => r.isViolation).length} violation candidate(s)
                      </span>
                    )}
                  </div>

                  {lastDetectionResult.riders && lastDetectionResult.riders.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {lastDetectionResult.riders.map((rider, idx) => (
                        <div key={rider.detectionId || idx} className="space-y-1">
                          <EvidenceCropImage
                            src={rider.cropPath}
                            alt={rider.label}
                            label={`Rider #${idx + 1}`}
                            subtitle={rider.detectionId}
                            confidence={rider.confidence}
                            aspectRatio="aspect-4/3"
                            badge={
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                rider.classification === 'WITHOUT_HELMET'
                                  ? 'bg-rose-100 text-rose-800 border border-rose-300'
                                  : rider.classification === 'WITH_HELMET'
                                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                    : 'bg-slate-100 text-slate-700 border border-slate-300'
                              }`}>
                                {rider.classification === 'WITHOUT_HELMET' 
                                  ? 'NO HELMET' 
                                  : rider.classification === 'WITH_HELMET' 
                                    ? 'WITH HELMET' 
                                    : 'UNKNOWN'}
                              </span>
                            }
                          />
                          <div className="flex items-center justify-between text-[10px] text-slate-500 px-1 font-mono">
                            <span>BBox: [{rider.bbox?.map(n => Math.round(n)).join(', ')}]</span>
                            {rider.isViolation && (
                              <span className="text-rose-600 font-bold uppercase text-[9px]">Flagged</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center text-[11px] text-slate-400">
                      No distinct rider bounding boxes detected in this frame.
                    </div>
                  )}
                </div>

                {/* License Plate Recognition & Crop */}
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[11px] text-slate-800 flex items-center gap-1.5">
                      <Radio className="w-3.5 h-3.5 text-amber-600" />
                      License Plate Recognition &amp; Crop
                    </span>
                    {lastDetectionResult.plateMatch?.matchStatus && (
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        lastDetectionResult.plateMatch.matchStatus === 'VERIFIED'
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                          : 'bg-amber-100 text-amber-800 border border-amber-300'
                      }`}>
                        {lastDetectionResult.plateMatch.matchStatus.replace('_', ' ')}
                      </span>
                    )}
                  </div>

                  {lastDetectionResult.plateMatch?.cropPath || lastDetectionResult.plateMatch?.plateDetected ? (
                    <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 p-2.5 rounded-lg border border-slate-200 bg-slate-50/70 items-center">
                      <div className="sm:col-span-5">
                        <EvidenceCropImage
                          src={lastDetectionResult.plateMatch.cropPath}
                          alt={lastDetectionResult.plateMatch.normalizedPlate || 'License Plate Crop'}
                          label="Plate Crop"
                          confidence={lastDetectionResult.plateMatch.confidence}
                          aspectRatio="aspect-16/9"
                          maxHeight="max-h-24"
                        />
                      </div>
                      <div className="sm:col-span-7 space-y-1.5 text-xs">
                        <div>
                          <span className="text-[10px] text-slate-400 block font-medium">Extracted Plate:</span>
                          <span className="font-mono font-bold text-sm text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200 inline-block">
                            {lastDetectionResult.plateMatch.normalizedPlate || lastDetectionResult.plateMatch.rawText || 'OCR UNRESOLVED'}
                          </span>
                        </div>
                        {lastDetectionResult.plateMatch.ownerNameSnapshot && (
                          <div className="text-[11px] text-slate-600">
                            <span className="text-slate-400">Reg Owner:</span> <span className="font-semibold text-slate-800">{lastDetectionResult.plateMatch.ownerNameSnapshot}</span>
                          </div>
                        )}
                        <div className="text-[10px] text-slate-500">
                          <span>Status: {lastDetectionResult.plateMatch.matchStatus}</span>
                          {lastDetectionResult.plateMatch.matchSource && (
                            <span> • Source: {lastDetectionResult.plateMatch.matchSource}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center text-[11px] text-slate-400">
                      No vehicle license plate detected in this frame.
                    </div>
                  )}
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
                      <span>Draft Case ID:</span>
                      <span className="font-mono font-bold text-slate-900">{lastDetectionResult.caseId}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>Reviewer Queue Ingestion:</span>
                    {lastDetectionResult.isDeduplicated ? (
                      <span className="text-amber-700 font-semibold flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> Suppressed (Cooldown)
                      </span>
                    ) : lastDetectionResult.savedToQueue ? (
                      <span className="text-emerald-700 font-semibold flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Queued (PENDING_REVIEW)
                      </span>
                    ) : (
                      <span className="text-slate-400 font-medium">
                        Not flagged (Compliant)
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <HelpCircle className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                <span>No frame analyzed yet. Start Periodic Monitoring or upload an image file to run genuine AI inference.</span>
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
                  {modelStatus?.helmetClassificationSupported ? 'Supported (With/Without Helmet)' : 'Unavailable'}
                </span>
              </div>
            </div>
          </div>

          {/* Recent Captures Strip */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-3 flex items-center justify-between">
              <span>Recent Analyzed Frames</span>
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
                      <div className="text-[11px] text-slate-500 truncate mt-0.5 flex items-center gap-1">
                        <span>Outcome: {c.outcome.replace(/_/g, ' ')}</span>
                        {c.isDeduplicated && (
                          <span className="text-[9px] bg-amber-100 text-amber-800 px-1 rounded font-semibold">
                            Deduplicated
                          </span>
                        )}
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
