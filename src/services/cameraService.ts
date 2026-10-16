import type { BoundingBox, ViolationCase, ViolationType } from '../types';
import { generateTrafficEvidenceSvg } from '../data/mockData';

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

  async startWebcam(videoElement: HTMLVideoElement, deviceId?: string): Promise<MediaStream> {
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
      await videoElement.play();
      return stream;
    } catch (err) {
      this.stopWebcam();
      throw err;
    }
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
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth || 640;
    canvas.height = videoElement.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('Canvas 2D context unavailable');
    }
    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
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
