import { clearTokens, getAccessToken } from './auth';
import type {
  Camera,
  TokenPair,
  Violation,
  ViolationDecision,
  ViolationListResponse,
} from './types';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type RequestOptions = Omit<RequestInit, 'headers' | 'body'> & {
  body?: unknown;
  headers?: Record<string, string>;
  auth?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, auth = true, ...rest } = options;

  const finalHeaders: Record<string, string> = { ...(headers ?? {}) };

  if (auth) {
    const token = getAccessToken();
    if (token) {
      finalHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
  }

  const response = await fetch(path, {
    ...rest,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && auth) {
    clearTokens();
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }

  if (!response.ok) {
    let message = `Ошибка запроса (${response.status})`;
    try {
      const data = await response.json();
      if (data && typeof data.detail === 'string') {
        message = data.detail;
      }
    } catch {
      // Тело ответа не является JSON — оставляем сообщение по умолчанию.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function login(login: string, password: string): Promise<TokenPair> {
  return request<TokenPair>('/api/v1/auth/login', {
    method: 'POST',
    body: { login, password },
    auth: false,
  });
}

export function listViolations(): Promise<ViolationListResponse> {
  return request<ViolationListResponse>('/api/v1/violations?limit=200', {
    method: 'GET',
  });
}

export function listCameras(): Promise<Camera[]> {
  return request<Camera[]>('/api/v1/cameras', {
    method: 'GET',
  });
}

export function sendFeedback(
  id: number,
  decision: ViolationDecision,
): Promise<Violation> {
  return request<Violation>(`/api/v1/violations/${id}/feedback`, {
    method: 'POST',
    body: { decision },
  });
}