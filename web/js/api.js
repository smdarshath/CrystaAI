export class ApiError extends Error { constructor(msg, code, status) { super(msg); this.code = code; this.status = status; } }

export function authHeader() {
  try { const t = localStorage.getItem('crysta_token'); return t ? { Authorization: 'Bearer ' + t } : {}; } catch { return {}; }
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  let res;
  try {
    res = await fetch(path, { method, signal, headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...authHeader() }, body: body ? JSON.stringify(body) : undefined });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError('Cannot reach the Crysta backend. Is run.py still running?', 'offline', 0);
  }
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) throw new ApiError(data?.error?.message || `Request failed (${res.status})`, data?.error?.code || 'error', res.status);
  return data;
}
