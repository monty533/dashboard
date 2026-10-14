export const API_BASE = (import.meta.env.VITE_BACKEND_API_URL || '').replace(/\/+$/, '');

export function authHeaders() {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Token ${token}` } : {}),
  };
}

export async function apiFetch(url, options = {}) {
  const { timeout = 30000, ...requestOptions } = options;
  const response = await fetch(url, {
    ...requestOptions,
    signal: options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(timeout)])
      : AbortSignal.timeout(timeout),
  });
  if (response.status === 401 && options.headers?.Authorization && options.headers.Authorization === authHeaders().Authorization) {
    window.dispatchEvent(new Event('auth-expired'));
  }
  return response;
}

export async function readJson(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.detail || 'Request failed.');
  return data;
}
