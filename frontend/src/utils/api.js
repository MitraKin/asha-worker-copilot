/**
 * API client utility — centralised fetch wrapper for all backend calls.
 */

const BASE_URL = '/api';

function getToken() {
  return localStorage.getItem('access_token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.clear();
    window.location.href = '/login';
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }

  return res.json();
}

// ── Auth ────────────────────────────────────────────────────────────────────
export const api = {
  auth: {
    login: (username, password) =>
      request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
    register: (data) =>
      request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
    confirm: (username, code) =>
      request('/auth/confirm', { method: 'POST', body: JSON.stringify({ username, code }) }),
    me: () => request('/auth/me'),
  },

  // ── Patients ──────────────────────────────────────────────────────────────
  patients: {
    list: () => request('/patients'),
    get: (id) => request(`/patients/${id}`),
    create: (data) => request('/patients', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/patients/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    history: (id) => request(`/patients/${id}/history`),
    stats: () => request('/patients/stats/summary'),
  },

  // ── Assessment ────────────────────────────────────────────────────────────
  assessment: {
    start: (data) => request('/assessment/start', { method: 'POST', body: JSON.stringify(data) }),
    sendText: (data) => request('/assessment/text', { method: 'POST', body: JSON.stringify(data) }),
    sendAudio: (data) => request('/assessment/audio', { method: 'POST', body: JSON.stringify(data) }),
    maternalRisk: (data) => request('/assessment/maternal-risk', { method: 'POST', body: JSON.stringify(data) }),
    getSession: (id) => request(`/assessment/session/${id}`),
  },

  // ── Vaccination ────────────────────────────────────────────────────────────
  vaccination: {
    generateSchedule: (id) => request(`/vaccination/${id}/generate-schedule`, { method: 'POST' }),
    getSchedule: (id) => request(`/vaccination/${id}/schedule`),
    record: (id, data) => request(`/vaccination/${id}/record`, { method: 'POST', body: JSON.stringify(data) }),
    dueVaccinations: (days = 7) => request(`/vaccination/reminders/due?days_ahead=${days}`),
    summary: (id) => request(`/vaccination/${id}/summary`),
  },
};
