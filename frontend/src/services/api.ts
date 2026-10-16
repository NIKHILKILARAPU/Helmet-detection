// Central API configuration and request wrapper for TrafficGuard AI

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  isDemoData: boolean;
  message?: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async isBackendLive(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      return res.ok;
    } catch {
      return false;
    }
  }

  async get<T>(endpoint: string, fallbackData: T): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
      }

      const json = await res.json();
      return {
        success: true,
        data: json.data || json,
        isDemoData: false
      };
    } catch {
      // Graceful fallback to demo data with clear transparency
      return {
        success: true,
        data: fallbackData,
        isDemoData: true,
        message: 'Operating in Demo Mode (Mock Data)'
      };
    }
  }

  async post<T, B = unknown>(endpoint: string, body: B, fallbackData: T): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
      }

      const json = await res.json();
      return {
        success: true,
        data: json.data || json,
        isDemoData: false
      };
    } catch {
      return {
        success: true,
        data: fallbackData,
        isDemoData: true,
        message: 'Simulated in Demo Mode'
      };
    }
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
