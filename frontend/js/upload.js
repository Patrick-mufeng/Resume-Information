/**
 * 上传与处理面板 - 文件上传、拖拽、处理控制
 */
import { api, connectProgressSocket } from './api.js';
import { showToast } from './key-manager.js';

const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const fileListCard = document.getElementById('file-list-card');
const fileCount = document.getElementById('file-count');
const processActions = document.getElementById('process-actions');
const startBtn = document.getElementById('start-btn');
const folderPathInput = document.getElementById('folder-path-input');
const scanFolderBtn = document.getElementById('scan-folder-btn');
const pauseBtn = document.getElementById('pause-btn');
const progressCard = document.getElementById('progress-card');
const logCard = document.getElementById('log-card');
const logStream = document.getElementById('log-stream');
const clearLogBtn = document.getElementById('clear-log-btn');
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const jobSelect = document.getElementById('job-select');
const newJobBtn = document.getElementById('new-job-btn');
const processDot = document.getElementById('process-dot');

let currentJobId = null;
let ws = null;
let uploadedFiles = [];
let isProcessing = false;
let isPaused = false;

// ==================== 任务管理 ====================
export async function refreshJobs() {
  try {
    const jobs = await api.listJobs();
    const current = jobSelect.value;
    jobSelect.innerHTML = '<option value="">-- 新建任务 --</option>';
    jobs.forEach(j => {
      jobSelect.innerHTML += `<option value="${j.id}" ${String(j.id) === current ? 'selected' : ''}>${j.name || `任务 #${j.id}`} (${j.status})</option>`;
    });
  } catch (e) {
    console.error('加载任务列表失败:', e);
  }
}

newJobBtn.addEventListener('click', async () => {
  try {
    const job = await api.createJob();
    await refreshJobs();
    jobSelect.value = job.id;
    selectJob(job.id);
    showToast('新任务已创建', 'success');
  } catch (e) {
    showToast(`创建失败: ${e.message}`, 'error');
  }
});

// ==================== 文件夹扫描处理 ====================
scanFolderBtn.addEventListener('click', async () => {
  const folderPath = folderPathInput.value.trim();
  if (!folderPath) {
    showToast('请输入文件夹路径', 'error');
    return;
  }

  scanFolderBtn.disabled = true;
  scanFolderBtn.textContent = '扫描转换中...';
  try {
    const result = await api.processFolderAndStart(folderPath);
    showToast(`扫描完成：${result.total} 份简历，处理已启动`, 'success');
    currentJobId = result.job_id;
    await refreshJobs();
    jobSelect.value = currentJobId;
    selectJob(currentJobId);
    startProgressUI();
    connectWS();
  } catch (e) {
    showToast(`处理失败: ${e.message}`, 'error');
  } finally {
    scanFolderBtn.disabled = false;
    scanFolderBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>扫描并处理`;
  }
});

// 文件夹路径回车触发
folderPathInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') scanFolderBtn.click();
});

jobSelect.addEventListener('change', () => {
  const id = jobSelect.value ? parseInt(jobSelect.value) : null;
  selectJob(id);
});

function selectJob(id) {
  currentJobId = id;
  uploadedFiles = [];
  fileList.innerHTML = '';
  fileListCard.style.display = id ? '' : 'none';
  processActions.style.display = id ? '' : 'none';
  progressCard.style.display = 'none';
  if (id) {
    refreshJobStatus();
  }
}

async function refreshJobStatus() {
  if (!currentJobId) return;
  try {
    const status = await api.getJobStatus(currentJobId);
    updateStats(status);
    if (status.status === 'running') {
      startProgressUI();
    }
  } catch (e) {
    console.error('获取任务状态失败:', e);
  }
}

// ==================== 文件上传 ====================
uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});

async function handleFiles(files) {
  if (files.length === 0) return;

  // 如果没有选中任务，自动创建
  if (!currentJobId) {
    try {
      const job = await api.createJob();
      await refreshJobs();
      jobSelect.value = job.id;
      currentJobId = job.id;
    } catch (e) {
      showToast(`创建任务失败: ${e.message}`, 'error');
      return;
    }
  }

  try {
    const result = await api.uploadFiles(Array.from(files), currentJobId);
    uploadedFiles.push(...result.uploaded);

    if (result.errors.length > 0) {
      result.errors.forEach(e => showToast(`${e.filename}: ${e.error}`, 'error'));
    }

    renderFileList();
    if (result.uploaded.length > 0) {
      showToast(`已上传 ${result.uploaded.length} 个文件`, 'success');
    }

    // 刷新任务
    await refreshJobs();
    jobSelect.value = currentJobId;
  } catch (e) {
    showToast(`上传失败: ${e.message}`, 'error');
  }
}

function renderFileList() {
  if (uploadedFiles.length === 0) {
    fileListCard.style.display = 'none';
    return;
  }

  fileListCard.style.display = '';
  fileCount.textContent = `${uploadedFiles.length} 个文件`;
  processActions.style.display = '';

  fileList.innerHTML = uploadedFiles.map((f, i) => `
    <div class="file-item" style="animation-delay:${i * 0.03}s">
      <div class="file-thumb">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.5">
          <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
      </div>
      <div class="file-info">
        <div class="file-name">${escapeHtml(f.filename)}</div>
        <div class="file-meta">${formatSize(f.size)}</div>
      </div>
      <span class="file-status pending">就绪</span>
    </div>
  `).join('');
}

// ==================== 处理控制 ====================
startBtn.addEventListener('click', async () => {
  if (!currentJobId) {
    showToast('请先创建任务并上传文件', 'error');
    return;
  }
  try {
    await api.startJob(currentJobId);
    startProgressUI();
    connectWS();
    showToast('处理已开始', 'success');
  } catch (e) {
    showToast(`启动失败: ${e.message}`, 'error');
  }
});

pauseBtn.addEventListener('click', async () => {
  if (!currentJobId) return;
  try {
    if (isPaused) {
      await api.resumeJob(currentJobId);
      pauseBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> 暂停`;
      isPaused = false;
      showToast('处理已恢复', 'success');
    } else {
      await api.pauseJob(currentJobId);
      pauseBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> 继续`;
      isPaused = true;
      showToast('处理已暂停', 'info');
    }
  } catch (e) {
    showToast(`操作失败: ${e.message}`, 'error');
  }
});

clearLogBtn.addEventListener('click', () => {
  logStream.innerHTML = '<div class="log-placeholder">日志已清空</div>';
});

function startProgressUI() {
  isProcessing = true;
  processDot.style.display = '';
  progressCard.style.display = '';
  logCard.style.display = '';
  startBtn.style.display = 'none';
  pauseBtn.style.display = '';
  pauseBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> 暂停`;
  isPaused = false;
}

function endProgressUI(errorMsg) {
  isProcessing = false;
  processDot.style.display = 'none';
  startBtn.style.display = '';
  pauseBtn.style.display = 'none';
  if (errorMsg) {
    showToast(errorMsg, 'error');
  }
}

function connectWS() {
  if (ws) ws.close();
  if (!currentJobId) return;

  let hasMessage = false;

  ws = connectProgressSocket(currentJobId, (msg) => {
    hasMessage = true;
    handleWSMessage(msg);

    if (msg.type === 'job_completed' || msg.type === 'job_error') {
      endProgressUI(msg.type === 'job_error' ? msg.error : null);
      if (ws) { ws.close(); ws = null; }
    }
  });

  // 安全网：即使 WebSocket 迟到，也通过 HTTP 轮询确保状态同步
  const checkInterval = setInterval(async () => {
    if (ws === null || !isProcessing) {
      clearInterval(checkInterval);
      return;
    }
    try {
      const status = await api.getJobStatus(currentJobId);
      updateStats(status);
      if (status.status === 'completed') {
        endProgressUI(null);
        if (ws) { ws.close(); ws = null; }
      } else if (status.status === 'failed') {
        endProgressUI('任务处理失败');
        if (ws) { ws.close(); ws = null; }
      }
    } catch (e) {
      // ignore poll errors
    }
  }, 2000);
}

function handleWSMessage(msg) {
  addLogEntry(msg);

  switch (msg.type) {
    case 'job_started':
      refreshJobStatus();
      break;
    case 'file_completed':
    case 'file_failed':
      refreshJobStatus();
      break;
    case 'job_completed':
      refreshJobStatus();
      break;
  }
}

function addLogEntry(msg) {
  // 移除占位文本
  const placeholder = logStream.querySelector('.log-placeholder');
  if (placeholder) placeholder.remove();

  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  let msgClass = 'info';
  let text = '';

  switch (msg.type) {
    case 'job_started':
      text = `开始处理任务`;
      break;
    case 'file_started':
      text = `开始处理: ${msg.filename}`;
      break;
    case 'file_completed':
      msgClass = 'success';
      text = `提取成功: ${msg.filename} → ${msg.name || '未知'} (${(msg.duration_ms / 1000).toFixed(1)}s)`;
      break;
    case 'file_failed':
      msgClass = 'error';
      text = `处理失败: ${msg.filename} - ${msg.error}`;
      break;
    case 'job_paused':
      text = `任务已暂停`;
      break;
    case 'job_resumed':
      text = `任务已恢复`;
      break;
    case 'job_completed':
      msgClass = msg.status === 'completed' ? 'success' : 'error';
      text = `任务完成: 已处理 ${msg.processed} 个, 失败 ${msg.failed} 个`;
      break;
    default:
      text = JSON.stringify(msg);
  }

  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `
    <span class="log-time">${time}</span>
    <span class="log-msg ${msgClass}">${escapeHtml(text)}</span>
  `;
  logStream.appendChild(entry);
  logStream.scrollTop = logStream.scrollHeight;
}

function updateStats(status) {
  const total = status.total_files || 0;
  const done = status.processed_count || 0;
  const failed = status.failed_count || 0;
  const pending = total - done - failed;

  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-done').textContent = done;
  document.getElementById('stat-failed').textContent = failed;
  document.getElementById('stat-pending').textContent = Math.max(0, pending);

  const pct = total > 0 ? Math.round((done + failed) / total * 100) : 0;
  progressBar.style.width = `${pct}%`;
  progressText.textContent = `${pct}%`;

  if (total > 0) {
    progressCard.style.display = '';
  }
}

// ==================== 工具函数 ====================
function formatSize(bytes) {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
  return bytes + ' B';
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
