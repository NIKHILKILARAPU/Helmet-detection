import { useState, useEffect, useRef, useCallback } from 'react';
import { cameraService } from '../services/cameraService';
import type { CameraDevice } from '../services/cameraService';

export const useCamera = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [availableDevices, setAvailableDevices] = useState<CameraDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('default');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    cameraService.getAvailableVideoDevices().then(devices => {
      setAvailableDevices(devices);
      if (devices.length > 0) {
        setSelectedDeviceId(devices[0].deviceId);
      }
    });

    return () => {
      cameraService.stopWebcam();
    };
  }, []);

  const startStream = useCallback(async (deviceId?: string) => {
    setErrorMessage(null);
    if (!videoRef.current) return;
    try {
      await cameraService.startWebcam(videoRef.current, deviceId || selectedDeviceId);
      setIsStreaming(true);
    } catch (err: any) {
      setIsStreaming(false);
      setErrorMessage(err.message || 'Failed to start camera');
      throw err;
    }
  }, [selectedDeviceId]);

  const stopStream = useCallback(() => {
    cameraService.stopWebcam();
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  }, []);

  const captureSnapshot = useCallback(() => {
    if (!videoRef.current || !isStreaming) return null;
    return cameraService.captureFrame(videoRef.current);
  }, [isStreaming]);

  return {
    videoRef,
    isStreaming,
    availableDevices,
    selectedDeviceId,
    setSelectedDeviceId,
    errorMessage,
    startStream,
    stopStream,
    captureSnapshot
  };
};
