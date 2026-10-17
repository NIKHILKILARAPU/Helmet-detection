import type { BoundingBox, ViolationCase, ViolationType } from '../types';
import { generateTrafficEvidenceSvg } from '../data/mockData';
import { apiClient } from './api';

export interface CameraDevice {
  deviceId: string;
  label: string;
}

class CameraService {
  private activeStream: MediaStream | null = null;

  async getAvailableVideoDevices(): Promise<CameraDevice[]> {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return [{ deviceId: 'default', label: 'Default Webcam' }];
      }
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = devices
        .filter(d => d.kind === 'videoinput')
        .map((d, index) => ({
          deviceId: d.deviceId || `cam-${index}`,
          label: d.label || `Camera ${index + 1} (${d.deviceId ? d.deviceId.substring(0, 6) : 'Integrated'})`
        }));
      return videoInputs.length > 0 ? videoInputs : [{ deviceId: 'default', label: 'Laptop Integrated Webcam' }];
    } catch {
      return [{ deviceId: 'default', label: 'Laptop Integrated Webcam' }];
    }
  }

  async startWebcam(
    videoElement: HTMLVideoElement,
    deviceId?: string,
    onStreamEnded?: () => void
  ): Promise<MediaStream> {
    this.stopWebcam();

    const constraints: MediaStreamConstraints = {
      video: deviceId && deviceId !== 'default' 
        ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
        : { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    };

    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.activeStream = stream;
      videoElement.srcObject = stream;

      // Listen for stream track termination (e.g. camera unplugged or revoked permissions)
      stream.getVideoTracks().forEach(track => {
        track.onended = () => {
          this.stopWebcam();
          if (onStreamEnded) {
            onStreamEnded();
          }
        };
      });

      await videoElement.play();

      // Wait for valid video metadata and dimensions (> 0) before allowing captures
      await this.waitForVideoDimensions(videoElement);

      return stream;
    } catch (err) {
      this.stopWebcam();
      throw err;
    }
  }

  /**
   * Waits until the video element has loaded metadata and nonzero optical dimensions.
   */
  async waitForVideoDimensions(
    videoElement: HTMLVideoElement,
    timeoutMs: number = 6000
  ): Promise<{ width: number; height: number }> {
    if (videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
      return { width: videoElement.videoWidth, height: videoElement.videoHeight };
    }

    return new Promise((resolve, reject) => {
      let resolved = false;
      const timeoutId = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          cleanup();
          if (videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
            resolve({ width: videoElement.videoWidth, height: videoElement.videoHeight });
          } else {
            reject(new Error('Hardware timeout: Video metadata and valid dimensions not received within 6 seconds.'));
          }
        }
      }, timeoutMs);

      const checkDimensions = () => {
        if (!resolved && videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
          resolved = true;
          cleanup();
          resolve({ width: videoElement.videoWidth, height: videoElement.videoHeight });
        }
      };

      const onMetadata = () => {
        checkDimensions();
      };

      const cleanup = () => {
        clearTimeout(timeoutId);
        videoElement.removeEventListener('loadedmetadata', onMetadata);
        videoElement.removeEventListener('playing', onMetadata);
      };

      videoElement.addEventListener('loadedmetadata', onMetadata);
      videoElement.addEventListener('playing', onMetadata);

      // Check immediately if already populated
      checkDimensions();
    });
  }

  stopWebcam(): void {
    if (this.activeStream) {
      this.activeStream.getTracks().forEach(track => {
        try {
          track.stop();
        } catch {
          // ignore
        }
      });
      this.activeStream = null;
    }
  }

  isStreaming(): boolean {
    return this.activeStream !== null && this.activeStream.active;
  }

  captureFrame(videoElement: HTMLVideoElement): string {
    const width = videoElement.videoWidth;
    const height = videoElement.videoHeight;
    if (!width || !height || width <= 0 || height <= 0) {
      throw new Error('Video dimensions are not ready (0x0). Please wait for camera stream.');
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('Canvas 2D context unavailable');
    }
    ctx.drawImage(videoElement, 0, 0, width, height);
    return canvas.toDataURL('image/jpeg', 0.85);
  }

  captureFrameBlob(videoElement: HTMLVideoElement): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const width = videoElement.videoWidth;
      const height = videoElement.videoHeight;
      if (!width || !height || width <= 0 || height <= 0) {
        return reject(new Error('Video dimensions are not ready (0x0). Please wait for camera stream.'));
      }

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        return reject(new Error('Canvas 2D context unavailable'));
      }
      ctx.drawImage(videoElement, 0, 0, width, height);
      canvas.toBlob(
        blob => {
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error('Failed to encode video frame canvas to JPEG blob.'));
          }
        },
        'image/jpeg',
        0.88
      );
    });
  }

  async analyzeFrame(
    imageFileOrBlob: File | Blob,
    cameraId?: string,
    sourceLabel: string = 'Operator Live Station',
    cooldownSeconds: number = 15
  ) {
    const formData = new FormData();
    if (imageFileOrBlob instanceof File) {
      formData.append('file', imageFileOrBlob, imageFileOrBlob.name);
    } else {
      formData.append('file', imageFileOrBlob, `webcam_frame_${Date.now()}.jpg`);
    }
    if (cameraId && cameraId !== 'default') {
      formData.append('camera_id', cameraId);
    }
    formData.append('source_label', sourceLabel);
    formData.append('auto_ingest', 'true');
    formData.append('cooldown_seconds', cooldownSeconds.toString());

    return apiClient.upload<any>('/detections/analyze', formData);
  }

  async getModelStatus() {
    return apiClient.get<any>('/detections/model-status', {
      isLoaded: false,
      classesCount: 0,
      helmetClassificationSupported: false,
    });
  }

  simulateCandidateDetection(
    snapshotUrl: string | null,
    sourceName: string = 'Operator Capture'
  ): {
    candidateCase: ViolationCase;
    outcomeType: 'NO_HELMET_CANDIDATE' | 'HELMET_DETECTED' | 'UNCERTAIN';
  } {
    const caseId = `TG-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    const now = new Date().toISOString().replace('T', ' ').substring(0, 19);

    // Realistic outcome distribution for testing
    const rand = Math.random();
    let outcomeType: 'NO_HELMET_CANDIDATE' | 'HELMET_DETECTED' | 'UNCERTAIN' = 'NO_HELMET_CANDIDATE';
    let violationType: ViolationType = 'NO_HELMET_RIDER';
    let confidence = 0.93;
    let bboxes: BoundingBox[] = [];

    if (rand < 0.6) {
      outcomeType = 'NO_HELMET_CANDIDATE';
      violationType = 'NO_HELMET_RIDER';
      confidence = 0.91 + Number((Math.random() * 0.07).toFixed(2));
      bboxes = [
        {
          id: `sim-bb-1`,
          label: 'NO_HELMET',
          confidence: confidence,
          x: 44,
          y: 32,
          width: 14,
          height: 18,
          color: '#DC2626'
        },
        {
          id: `sim-bb-2`,
          label: 'RIDER',
          confidence: 0.96,
          x: 38,
          y: 25,
          width: 26,
          height: 52,
          color: '#2563EB'
        }
      ];
    } else if (rand < 0.85) {
      outcomeType = 'HELMET_DETECTED';
      violationType = 'HELMET_STRAP_UNFASTENED';
      confidence = 0.95;
      bboxes = [
        {
          id: `sim-bb-1`,
          label: 'HELMET',
          confidence: 0.95,
          x: 44,
          y: 32,
          width: 14,
          height: 18,
          color: '#15803D'
        }
      ];
    } else {
      outcomeType = 'UNCERTAIN';
      violationType = 'HELMET_STRAP_UNFASTENED';
      confidence = 0.54;
      bboxes = [
        {
          id: `sim-bb-1`,
          label: 'NO_HELMET',
          confidence: 0.54,
          x: 42,
          y: 30,
          width: 15,
          height: 19,
          color: '#F59E0B'
        }
      ];
    }

    const candidateCase: ViolationCase = {
      id: caseId,
      timestamp: now,
      camera: {
        id: 'CAM-LIVE-SIM',
        name: sourceName,
        location: 'Operator Workspace Testing Feed',
        type: 'WEBCAM'
      },
      violationType,
      confidence,
      status: 'PENDING_REVIEW',
      evidenceImageUrl: snapshotUrl || generateTrafficEvidenceSvg('NO_HELMET', caseId),
      evidenceQuality: 'HIGH',
      boundingBoxes: bboxes,
      linkedPerson: {
        personId: 'PID-77319',
        fullName: 'Aditya Sharma',
        maskedMobile: '+91 98*** **412',
        vehiclePlate: 'KA 01 MJ 4892',
        vehicleModel: 'Honda Activa 6G',
        identityVerified: true,
        registrationDate: '2023-04-12'
      },
      reviewerNotes: '',
      reviewHistory: [
        {
          id: `audit-${Date.now()}`,
          timestamp: now,
          actor: 'Operator Simulation / Pipeline Test',
          role: 'operator',
          action: 'CREATED',
          notes: 'Candidate frame captured in operator testing mode.'
        }
      ]
    };

    return { candidateCase, outcomeType };
  }
}

export const cameraService = new CameraService();
