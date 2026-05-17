/**
 * API Key 管理面板
 */
import { api } from './api.js';

const keyInput = document.getElementById('key-input');
const keyLabelInput = document.getElementById('key-label-input');
const addKeyBtn = document.getElementById('add-key-btn');
const toggleVisBtn = document.getElementById('toggle-key-vis');
const keyList = document.getElementById('key-list');
const keysEmpty = document.getElementById('keys-empty');
const keyCountBadge = document.getElementById('key-count-badge');
const providerSelect = document.getElementById('provider-select');
const customUrlGroup = document.getElementById('custom-url-group');
const customUrlInput = document.getElementById('custom-url-input');
const customModelGroup = document.getElementById('custom-model-group');
const customModelInput = document.getElementById('custom-model-input');

let keys = [];

const PROVIDER_NAMES = {
  moonshot: 'Moonshot',
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  anthropic: 'Claude',
  gemini: 'Gemini',
  custom: 'Custom',
};

const PROVIDER_PLACEHOLDERS = {
  moonshot: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
  openai: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
  deepseek: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
  anthropic: 'sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx',
  gemini: 'AIza...xxxxxxxxxxxxxxxxxxxxxxxx',
  custom: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
};

// 提供商切换
providerSelect.addEventListener('change', () => {
  const isCustom = providerSelect.value === 'custom';
  customUrlGroup.style.display = isCustom ? '' : 'none';
  customModelGroup.style.display = isCustom ? '' : 'none';
  keyInput.placeholder = PROVIDER_PLACEHOLDERS[providerSelect.value] || '请输入 API Key';
});

// 切换 Key 显示/隐藏
toggleVisBtn.addEventListener('click', () => {
  keyInput.type = keyInput.type === 'password' ? 'text' : 'password';
});

// 添加 Key
addKeyBtn.addEventListener('click', async () => {
  const value = keyInput.value.trim();
  const provider = providerSelect.value;

  if (!value) {
    showToast('请输入 API Key', 'error');
    return;
  }

  // Custom provider 必须填写 url 和 model
  if (provider === 'custom') {
    if (!customUrlInput.value.trim() || !customModelInput.value.trim()) {
      showToast('Custom 提供商必须填写 Base URL 和 Model Name', 'error');
      return;
    }
  }

  addKeyBtn.disabled = true;
  try {
    const result = await api.addKey(
      value,
      keyLabelInput.value.trim(),
      provider,
      customUrlInput.value.trim() || null,
      customModelInput.value.trim() || null,
    );
    const savedId = result.id;
    keyInput.value = '';
    keyLabelInput.value = '';
    customUrlInput.value = '';
    customModelInput.value = '';
    await refreshKeys();

    // 自动检测 Key 可用性
    try {
      const checkResult = await api.checkKey(savedId);
      if (checkResult.is_valid === true) {
        showToast('Key 添加成功 — 可用', 'success');
      } else if (checkResult.is_valid === false) {
        showToast(`Key 添加成功 — 但不可用: ${checkResult.error}`, 'error');
      } else {
        showToast(`Key 已添加（${checkResult.error || '无法验证可用性'}）`, 'info');
      }
      await refreshKeys();
    } catch (e) {
      showToast('Key 添加成功（验证失败，请手动检查）', 'info');
    }
  } catch (e) {
    showToast(`添加失败: ${e.message}`, 'error');
  } finally {
    addKeyBtn.disabled = false;
  }
});

// Enter 快速添加
keyInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addKeyBtn.click();
});

// 渲染 Key 列表
function renderKeys() {
  if (keys.length === 0) {
    keysEmpty.style.display = '';
    keyCountBadge.textContent = '0';
    return;
  }

  keysEmpty.style.display = 'none';
  keyCountBadge.textContent = keys.length;

  const html = keys.map((k, idx) => {
    let indicatorClass, indicatorTitle;
    if (k.is_validated === true) {
      indicatorClass = 'ok';
      indicatorTitle = 'Key 可用';
    } else if (k.is_validated === false) {
      indicatorClass = 'error';
      indicatorTitle = 'Key 无效: ' + (k.last_check_error || '未知错误');
    } else {
      indicatorClass = 'unchecked';
      indicatorTitle = k.last_check_error ? '无法验证: ' + k.last_check_error : '尚未检查';
    }
    // 连续错误覆盖（运行时问题）
    if (k.consecutive_errors >= 3) {
      indicatorClass = 'error';
      indicatorTitle = '连续调用失败，暂不可用';
    }

    return `
      <div class="key-card ${k.is_validated === false ? 'status-error' : ''}" style="animation-delay:${idx * 0.05}s">
        <div class="key-indicator ${indicatorClass}" title="${escapeHtml(indicatorTitle)}"></div>
        <div class="key-info">
          <div class="key-value">${escapeHtml(k.key_masked)}</div>
          <div>
            ${k.label ? `<span class="key-label-tag">${escapeHtml(k.label)}</span>` : ''}
            <span class="key-provider-tag">${PROVIDER_NAMES[k.provider] || k.provider || 'Moonshot'}</span>
          </div>
        </div>
        <div class="key-stats">
          <div class="key-stat">
            <span class="key-stat-val">${k.requests_today || 0}</span>
            <span class="key-stat-label">今日请求</span>
          </div>
          <div class="key-stat">
            <span class="key-stat-val">${formatTokens(k.tokens_today || 0)}</span>
            <span class="key-stat-label">今日 Token</span>
          </div>
        </div>
        <div class="key-actions">
          <button class="btn-icon check-btn" data-key-id="${k.id}" title="检查可用性">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="check-icon-${k.id}">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </button>
          <label class="toggle" title="${k.is_active ? '禁用' : '启用'}">
            <input type="checkbox" ${k.is_active ? 'checked' : ''} data-key-id="${k.id}">
            <span class="toggle-slider"></span>
          </label>
          <button class="key-remove-btn" data-key-id="${k.id}" title="删除">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join('');

  keyList.innerHTML = html;

  // 检查按钮事件
  keyList.querySelectorAll('.check-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = parseInt(btn.dataset.keyId);
      const icon = btn.querySelector('svg');
      btn.disabled = true;
      icon.classList.add('spinning');

      try {
        const result = await api.checkKey(id);
        if (result.is_valid === true) {
          showToast('Key 可用', 'success');
        } else if (result.is_valid === false) {
          showToast(`Key 无效: ${result.error || '未知原因'}`, 'error');
        } else {
          showToast(`无法验证: ${result.error || '网络异常'}`, 'info');
        }
        await refreshKeys();
      } catch (err) {
        showToast(`检查失败: ${err.message}`, 'error');
      } finally {
        btn.disabled = false;
        icon.classList.remove('spinning');
      }
    });
  });

  // 开关事件
  keyList.querySelectorAll('.toggle input').forEach(toggle => {
    toggle.addEventListener('change', async (e) => {
      const id = e.target.dataset.keyId;
      try {
        await api.toggleKey(id);
        await refreshKeys();
      } catch (err) {
        showToast(`操作失败: ${err.message}`, 'error');
        e.target.checked = !e.target.checked;
      }
    });
  });

  // 删除事件
  keyList.querySelectorAll('.key-remove-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.keyId;
      if (!(await showConfirm('确定要删除这个 API Key 吗？'))) return;
      try {
        await api.deleteKey(id);
        await refreshKeys();
        showToast('已删除', 'success');
      } catch (err) {
        showToast(`删除失败: ${err.message}`, 'error');
      }
    });
  });
}

function calcStats(key) {
  const tpd = 1500000;
  const tpm = 32000;
  return {
    usage: key.tokens_today / tpd,
    rpmUsage: key.tpm_used / tpm,
  };
}

function formatTokens(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

export async function refreshKeys() {
  try {
    keys = await api.listKeys();
    renderKeys();
  } catch (e) {
    console.error('加载 Key 列表失败:', e);
  }
}

export function showToast(msg, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

export function showConfirm(message) {
  return new Promise((resolve) => {
    const modal = document.getElementById('confirm-modal');
    const msgEl = document.getElementById('confirm-message');
    const cancelBtn = document.getElementById('confirm-cancel-btn');
    const okBtn = document.getElementById('confirm-ok-btn');

    msgEl.textContent = message;
    modal.style.display = '';

    function cleanup(result) {
      modal.style.display = 'none';
      cancelBtn.removeEventListener('click', onCancel);
      okBtn.removeEventListener('click', onOk);
      modal.removeEventListener('click', onOverlay);
      resolve(result);
    }

    function onCancel() { cleanup(false); }
    function onOk() { cleanup(true); }
    function onOverlay(e) { if (e.target === modal) cleanup(false); }

    cancelBtn.addEventListener('click', onCancel);
    okBtn.addEventListener('click', onOk);
    modal.addEventListener('click', onOverlay);
  });
}
