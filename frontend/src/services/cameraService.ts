import type { CameraSourceRecord } from '../types';
import { apiClient } from './api';

export interface CameraDevice {
  deviceId: string;
  label: string;
}

export function mapBackendCamera(doc: any): CameraSourceRecord {
  const lastHb = doc.lastHeartbeatAt 
    ? new Date(doc.lastHeartbeatAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : 'Just now';

  return {
    id: doc.id || (doc._id ? String(doc._id) : 'CAM-01'),
    name: doc.name || 'Surveillance Feed',
    junction: doc.junction || 'Junction Checkpoint',
    streamType: (doc.streamType as any) || 'WEBCAM',
    status: (doc.status as any) || 'STANDBY',
    ipOrDeviceUrl: doc.source || doc.ipOrDeviceUrl || 'video-device-0',
    resolution: doc.resolution || '1080p',
    fps: typeof doc.fps === 'number' ? doc.fps : 30,
    dailyDetectionsCount: doc.dailyDetectionsCount ?? 0,
    lastHeartbeat: lastHb
  };
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
    return apiClient.get<any>('/detections/model-status');
  }

  async getCameras(): Promise<{ cameras: CameraSourceRecord[]; success: boolean; error?: string }> {
    const res = await apiClient.get<any[]>('/cameras');
    if (!res.success || !res.data) {
      return { cameras: [], success: false, error: res.error || 'Failed to fetch camera feeds from server.' };
    }
    const rawList = Array.isArray(res.data) ? res.data : [];
    return { cameras: rawList.map(mapBackendCamera), success: true };
  }

  async registerCamera(payload: {
    name: string;
    junction: string;
    streamType: string;
    ipOrDeviceUrl: string;
    resolution?: string;
    fps?: number;
  }): Promise<{ success: boolean; camera?: CameraSourceRecord; error?: string }> {
    const res = await apiClient.post<any>('/cameras', payload);
    if (!res.success || !res.data) {
      return { success: false, error: res.error || 'Failed to register camera in database.' };
    }
    return { success: true, camera: mapBackendCamera(res.data) };
  }
}

export const cameraService = new CameraService();
