/**
 * API 通信层 - 封装所有后端 API 和 WebSocket 调用
 */

const BASE = '/api';

export const api = {
  // ==================== Keys ====================
  async listKeys() {
    const res = await fetch(`${BASE}/keys`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async addKey(keyValue, label, provider = 'moonshot', baseUrlOverride = null, modelOverride = null) {
    const body = {
      key_value: keyValue,
      label,
      provider,
      base_url_override: baseUrlOverride || null,
      model_override: modelOverride || null,
    };
    const res = await fetch(`${BASE}/keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async deleteKey(id) {
    const res = await fetch(`${BASE}/keys/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async toggleKey(id) {
    const res = await fetch(`${BASE}/keys/${id}/toggle`, { method: 'PATCH' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async checkKey(id) {
    const res = await fetch(`${BASE}/keys/${id}/check`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async checkAllKeys() {
    const res = await fetch(`${BASE}/keys/check-all`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // ==================== Jobs ====================
  async listJobs() {
    const res = await fetch(`${BASE}/jobs`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async createJob(name = '') {
    const res = await fetch(`${BASE}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async processFolderAndStart(folderPath) {
    const params = new URLSearchParams({ folder_path: folderPath });
    const res = await fetch(`${BASE}/resumes/process-folder/start?${params}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async getJobStatus(jobId) {
    const res = await fetch(`${BASE}/jobs/${jobId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async startJob(jobId) {
    const res = await fetch(`${BASE}/jobs/${jobId}/start`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async pauseJob(jobId) {
    const res = await fetch(`${BASE}/jobs/${jobId}/pause`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async resumeJob(jobId) {
    const res = await fetch(`${BASE}/jobs/${jobId}/resume`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  // ==================== Resumes ====================
  async listResumes({ page = 1, pageSize = 50, status = '', search = '' } = {}) {
    const params = new URLSearchParams({ page, page_size: pageSize });
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    const res = await fetch(`${BASE}/resumes?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async uploadFiles(files, jobId) {
    const form = new FormData();
    for (const f of files) {
      form.append('files', f);
    }
    const url = jobId ? `${BASE}/resumes/upload?job_id=${jobId}` : `${BASE}/resumes/upload`;
    const res = await fetch(url, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async retryResume(id) {
    const res = await fetch(`${BASE}/resumes/${id}/retry`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  async deleteResume(id) {
    const res = await fetch(`${BASE}/resumes/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  getExportUrl(jobId) {
    const params = jobId ? `?job_id=${jobId}` : '';
    return `${BASE}/resumes/export/csv${params}`;
  },

  // ==================== Health ====================
  async healthCheck() {
    const res = await fetch(`${BASE}/health`);
    return res.json();
  },
};

/**
 * WebSocket 连接管理
 */
export function connectProgressSocket(jobId, onMessage) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${location.host}/ws/progress/${jobId}`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error('WebSocket 消息解析失败:', e);
    }
  };

  ws.onclose = () => {
    console.log('WebSocket 已断开');
  };

  ws.onerror = (err) => {
    console.error('WebSocket 错误:', err);
  };

  return ws;
}
