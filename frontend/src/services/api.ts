export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

/**
 * Resolves a backend-relative media path (e.g. '/uploads/evidence/...')
 * or external URL into a fully-qualified URL against the backend origin.
 * Prevents requests from incorrectly targeting the Vite development server origin.
 */
export function getMediaUrl(path?: string | null): string {
  if (!path) return '';
  const trimmed = path.trim();
  if (!trimmed) return '';
  // If already absolute or blob/data URI, return directly
  if (
    trimmed.startsWith('http://') ||
    trimmed.startsWith('https://') ||
    trimmed.startsWith('blob:') ||
    trimmed.startsWith('data:')
  ) {
    return trimmed;
  }
  // If path is a local file pseudo-protocol from write failures, cannot be fetched over HTTP
  if (trimmed.startsWith('file://')) {
    return '';
  }
  // Strip trailing slashes and /api/v1 prefix from API_BASE_URL to resolve to root backend origin
  const backendOrigin = API_BASE_URL.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '');
  const cleanPath = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return `${backendOrigin}${cleanPath}`;
}

/**
 * Fetches an image securely with Bearer token authentication in the Authorization header.
 * Token is NEVER appended to query parameters, preventing URL/log credential leakage.
 * Returns an object URL that caller can revoke via URL.revokeObjectURL when unmounted.
 */
export async function fetchAuthenticatedBlobUrl(pathOrUrl: string): Promise<string> {
  const fullUrl = getMediaUrl(pathOrUrl);
  if (!fullUrl) throw new Error('Invalid image path');

  const token = apiClient.getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(fullUrl, {
    method: 'GET',
    headers,
  });

  if (!res.ok) {
    throw new Error(`Failed to load evidence image (HTTP ${res.status} ${res.statusText})`);
  }

  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
  errorCode?: string;
  isDemoData?: boolean;
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
    this.cleanupObsoleteStorage();
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  getAuthToken(): string | null {
    try {
      const token = localStorage.getItem(this.tokenKey);
      if (!token || token === 'null' || token === 'undefined' || !token.trim()) {
        return null;
      }
      return token.trim();
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

  cleanupObsoleteStorage(): void {
    try {
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (
          key &&
          (key.startsWith('demo_') ||
            key.startsWith('mock_') ||
            key.startsWith('test_') ||
            key === 'trafficguard_demo_mode' ||
            key === 'trafficguard_mock_cases' ||
            key === 'trafficguard_sample_data')
        ) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(k => localStorage.removeItem(k));
    } catch {
      // ignore
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

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        headers: {
          ...this.getAuthHeaders(),
        },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        return {
          success: false,
          error: json?.message || `Server returned HTTP ${res.status}`,
          errorCode: json?.error_code || `HTTP_${res.status}`,
          isDemoData: false
        };
      }

      return {
        success: true,
        data: json?.data !== undefined ? json.data : json,
        message: json?.message,
        isDemoData: false
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || 'Network request failed. Ensure backend is running.',
        errorCode: 'NETWORK_ERROR',
        isDemoData: false
      };
    }
  }

  async post<T, B = unknown>(endpoint: string, body: B): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
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

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        return {
          success: false,
          error: json?.message || `Server returned HTTP ${res.status}`,
          errorCode: json?.error_code || `HTTP_${res.status}`,
          isDemoData: false
        };
      }

      return {
        success: true,
        data: json?.data !== undefined ? json.data : json,
        message: json?.message,
        isDemoData: false
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || 'Network request failed.',
        errorCode: 'NETWORK_ERROR',
        isDemoData: false
      };
    }
  }

  async patch<T, B = unknown>(endpoint: string, body: B): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        return {
          success: false,
          error: json?.message || `Server returned HTTP ${res.status}`,
          errorCode: json?.error_code || `HTTP_${res.status}`,
          isDemoData: false
        };
      }

      return {
        success: true,
        data: json?.data !== undefined ? json.data : json,
        message: json?.message,
        isDemoData: false
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || 'Network request failed.',
        errorCode: 'NETWORK_ERROR',
        isDemoData: false
      };
    }
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'DELETE',
        headers: {
          ...this.getAuthHeaders(),
        },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        return {
          success: false,
          error: json?.message || `Server returned HTTP ${res.status}`,
          errorCode: json?.error_code || `HTTP_${res.status}`,
          isDemoData: false
        };
      }

      return {
        success: true,
        data: json?.data !== undefined ? json.data : json,
        message: json?.message,
        isDemoData: false
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || 'Network request failed.',
        errorCode: 'NETWORK_ERROR',
        isDemoData: false
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
      const isFetchErr = err?.name === 'TypeError' || (err?.message && /fetch/i.test(err.message));
      const helpfulMsg = isFetchErr
        ? `Unable to connect to backend at ${this.baseUrl}${endpoint}. Ensure FastAPI is running at http://127.0.0.1:8000 and CORS permits this origin.`
        : (err.message || 'Network request failed. Ensure FastAPI backend is running on port 8000.');
      return {
        success: false,
        error: helpfulMsg,
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
