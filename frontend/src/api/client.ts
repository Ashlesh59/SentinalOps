const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
export const DEMO_TENANT_ID = import.meta.env.VITE_DEMO_TENANT_ID || 'tenant-test';

class ApiError extends Error {
  public status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');
  headers.set('Accept', 'application/json');

  const config: RequestInit = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      let errorMsg = response.statusText;
      try {
        const errData = await response.json();
        errorMsg = errData.detail || errorMsg;
      } catch (e) {
        // ignore JSON parse error on error response
      }
      throw new ApiError(response.status, errorMsg);
    }
    
    // Support 202 Accepted which might return empty body or json
    const text = await response.text();
    if (!text) return {} as T;
    
    return JSON.parse(text) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error(`Network error: ${(error as Error).message}`);
  }
}

export const apiClient = {
  get: <T>(endpoint: string) => request<T>(endpoint, { method: 'GET' }),
  post: <T>(endpoint: string, body?: any) => request<T>(endpoint, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(endpoint: string, body: any) => request<T>(endpoint, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(endpoint: string) => request<T>(endpoint, { method: 'DELETE' }),
};
