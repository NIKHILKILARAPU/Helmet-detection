// Central API configuration and request wrapper for TrafficGuard AI

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  isDemoData: boolean;
  message?: string;
  errorCode?: string;
}

export interface ApiErrorDetail {
  field?: string;
  message?: string;
  error_type?: string;
}

export interface ApiUploadResult<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
  errorCode?: string;
  details?: ApiErrorDetail[];
}

class ApiClient {
  private baseUrl: string;
  private tokenKey = 'trafficguard_jwt_token';

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  getAuthToken(): string | null {
    try {
      return localStorage.getItem(this.tokenKey);
    } catch {
      return null;
    }
  }

  setAuthToken(token: string | null): void {
    try {
      if (token) {
        localStorage.setItem(this.tokenKey, token);
      } else {
        localStorage.removeItem(this.tokenKey);
      }
    } catch {
      // ignore local storage restrictions
    }
  }

  private getAuthHeaders(): Record<string, string> {
    const token = this.getAuthToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async isBackendLive(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
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
        headers: {
          ...this.getAuthHeaders(),
        },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
      }

      const json = await res.json();
      return {
        success: true,
        data: json.data || json,
        isDemoData: false,
      };
    } catch {
      // Graceful fallback to demo data with clear transparency
      return {
        success: true,
        data: fallbackData,
        isDemoData: true,
        message: 'Operating in Demo Mode (Mock Data)',
      };
    }
  }

  async post<T, B = unknown>(endpoint: string, body: B, fallbackData: T): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
      }

      const json = await res.json();
      return {
        success: true,
        data: json.data || json,
        isDemoData: false,
      };
    } catch {
      return {
        success: true,
        data: fallbackData,
        isDemoData: true,
        message: 'Simulated in Demo Mode',
      };
    }
  }

  /**
   * Uploads multipart/form-data to FastAPI without silent mock fallbacks.
   * Accurately propagates real HTTP errors, MODEL_NOT_AVAILABLE, and validation failures.
   */
  async upload<T>(endpoint: string, formData: FormData): Promise<ApiUploadResult<T>> {
    try {
      const token = this.getAuthToken();
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers,
        body: formData,
      });

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        const errorMsg = json?.message || `Server returned HTTP ${res.status} ${res.statusText}`;
        const errorCode = json?.error_code || `HTTP_${res.status}`;
        const details = json?.details || [];
        return {
          success: false,
          error: errorMsg,
          errorCode: errorCode,
          details: details,
        };
      }

      return {
        success: true,
        data: json.data || json,
        message: json.message,
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || 'Network request failed. Ensure FastAPI backend is running on port 8000.',
        errorCode: 'NETWORK_ERROR',
      };
    }
  }

  /**
   * Authenticates against FastAPI /auth/login and stores JWT token in localStorage.
   */
  async login(email: string, password: string): Promise<{ success: boolean; token?: string; error?: string }> {
    try {
      const res = await fetch(`${this.baseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const json = await res.json().catch(() => null);
      if (!res.ok) {
        return {
          success: false,
          error: json?.message || 'Login failed. Please verify credentials.',
        };
      }

      const token = json?.data?.accessToken;
      if (token) {
        this.setAuthToken(token);
        return { success: true, token };
      }
      return { success: false, error: 'Token missing in server response.' };
    } catch (err: any) {
      return { success: false, error: err.message || 'Network error during authentication.' };
    }
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
