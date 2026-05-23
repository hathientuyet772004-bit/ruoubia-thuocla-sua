import axios from 'axios';

const API_BASE = '/api';

export function classifyApiError(error) {
  const status = error?.response?.status;
  if (status === 401 || status === 403) return { kind: 'permission', message: error?.response?.data?.detail || 'Phiên quản trị không còn hợp lệ.' };
  return { kind: 'error', message: error?.response?.data?.detail || error?.message || 'Không gọi được API.' };
}

export function expectApiList(value, endpoint) {
  if (Array.isArray(value)) return value;
  throw new Error(`${endpoint} không trả về danh sách JSON. Hãy mở Admin Center qua reverse proxy.`);
}

export function fetchApiList(endpoint, config) {
  return axios.get(`${API_BASE}${endpoint}`, config).then((response) => expectApiList(response.data, endpoint));
}
