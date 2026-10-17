import type { SystemHealthState } from '../types';
import { apiClient } from './api';

export const INITIAL_SYSTEM_HEALTH_CLEAN: SystemHealthState = {
  api: {
    status: 'ONLINE',
    responseTimeMs: 0,
    lastChecked: 'Initializing...',
    message: 'Connecting to enforcement gateway...'
  },
  database: {
    status: 'ONLINE',
    responseTimeMs: 0,
    lastChecked: 'Initializing...',
    message: 'Verifying MongoDB replica set...'
  },
  model: {
    status: 'READY',
    responseTimeMs: 0,
    lastChecked: 'Initializing...',
    message: 'Verifying inference engine...'
  },
  camera: {
    status: 'ONLINE',
    lastChecked: 'Initializing...',
    message: 'Live hardware capture ready'
  },
  isBackendConnected: false,
  isDemoMode: false
};

class HealthService {
  async checkHealth(): Promise<SystemHealthState> {
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const res = await apiClient.get<any>('/health');

    if (res.success && res.data) {
      const data = res.data;
      const dbInfo = data.database || {};
      const dbStatus = dbInfo.status === 'ONLINE' ? 'ONLINE' : 'OFFLINE';
      const modelStatus = (data.yolo_model === 'READY' || data.yolo_model === 'ONLINE') ? 'READY' : 'OFFLINE';

      return {
        api: {
          status: data.status === 'ONLINE' ? 'ONLINE' : 'DEGRADED',
          responseTimeMs: dbInfo.latency_ms || 1,
          lastChecked: now,
          message: data.message || 'All enforcement microservices operational'
        },
        database: {
          status: dbStatus,
          responseTimeMs: dbInfo.latency_ms || 0,
          lastChecked: now,
          message: dbInfo.is_ready ? `Connected to ${dbInfo.database || 'helmet_challan_db'}` : (dbInfo.error || 'Database unavailable')
        },
        model: {
          status: modelStatus,
          lastChecked: now,
          message: modelStatus === 'READY' ? 'Inference engine operational' : 'Model weights or API key unconfigured'
        },
        camera: {
          status: 'ONLINE',
          lastChecked: now,
          message: 'Video hardware interface ready'
        },
        isBackendConnected: true,
        isDemoMode: false
      };
    }

    return {
      api: {
        status: 'OFFLINE',
        lastChecked: now,
        message: res.error || 'Cannot reach FastAPI backend (port 8000)'
      },
      database: {
        status: 'OFFLINE',
        lastChecked: now,
        message: 'Backend gateway unreachable'
      },
      model: {
        status: 'OFFLINE',
        lastChecked: now,
        message: 'Backend gateway unreachable'
      },
      camera: {
        status: 'OFFLINE',
        lastChecked: now,
        message: 'Camera service standby'
      },
      isBackendConnected: false,
      isDemoMode: false
    };
  }
}

export const healthService = new HealthService();
