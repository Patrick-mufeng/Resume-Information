/**
 * 应用主入口 - 初始化、标签页导航、状态管理
 */
import { api } from './api.js';
import { refreshKeys } from './key-manager.js';
import { refreshJobs } from './upload.js';
import { refreshResults } from './results.js';
import { refreshFields } from './settings.js';

const sidebar = document.getElementById('sidebar');
const backendStatus = document.getElementById('backend-status');
const tabContents = document.querySelectorAll('.tab-content');
const navItems = document.querySelectorAll('.nav-item');

// ==================== 导航切换 ====================
navItems.forEach(item => {
  item.addEventListener('click', () => {
    const tab = item.dataset.tab;

    // 更新导航状态
    navItems.forEach(n => n.classList.remove('active'));
    item.classList.add('active');

    // 切换内容区
    tabContents.forEach(tc => tc.classList.remove('active'));
    const target = document.getElementById(`tab-${tab}`);
    if (target) target.classList.add('active');

    // 懒加载各面板
    if (tab === 'keys') refreshKeys();
    if (tab === 'process') refreshJobs();
    if (tab === 'fields') refreshFields();
    if (tab === 'results') refreshResults();
  });
});

// ==================== 后端健康检查 ====================
async function checkHealth() {
  try {
    const health = await api.healthCheck();
    const dot = backendStatus.querySelector('.status-dot');
    const text = backendStatus.querySelector('.status-text');

    dot.classList.remove('offline');
    dot.classList.add('online');
    text.textContent = `后端已连接 (${health.key_count} Key)`;
  } catch (e) {
    const dot = backendStatus.querySelector('.status-dot');
    const text = backendStatus.querySelector('.status-text');

    dot.classList.remove('online');
    dot.classList.add('offline');
    text.textContent = '后端未连接';
  }
}

// ==================== 初始化 ====================
async function init() {
  await checkHealth();
  await refreshKeys();
  // 默认显示 Key 管理
  document.getElementById('tab-keys').classList.add('active');

  // 定时健康检查
  setInterval(checkHealth, 30000);

  // ==================== 使用说明弹窗 ====================
  const helpModal = document.getElementById('help-modal');
  const helpClose = document.getElementById('help-modal-close');

  document.querySelectorAll('.btn-help').forEach(btn => {
    btn.addEventListener('click', () => {
      const helpId = btn.dataset.help;
      helpModal.querySelectorAll('.help-content').forEach(c => c.style.display = 'none');
      const target = document.getElementById('help-' + helpId);
      if (target) target.style.display = 'block';
      helpModal.style.display = 'flex';
    });
  });

  helpClose.addEventListener('click', () => {
    helpModal.style.display = 'none';
  });

  helpModal.addEventListener('click', (e) => {
    if (e.target === helpModal) helpModal.style.display = 'none';
  });
}

init();
