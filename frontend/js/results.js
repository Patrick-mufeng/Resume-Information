/**
 * 结果查看面板 - 数据表格、搜索、导出
 */
import { api } from './api.js';
import { showToast, showConfirm } from './key-manager.js';

const resultsBody = document.getElementById('results-body');
const searchInput = document.getElementById('search-input');
const statusFilter = document.getElementById('status-filter');
const exportBtn = document.getElementById('export-btn');
const prevPageBtn = document.getElementById('prev-page');
const nextPageBtn = document.getElementById('next-page');
const pageInfo = document.getElementById('page-info');
const pagination = document.getElementById('pagination');
const resultCountBadge = document.getElementById('result-count-badge');
const detailModal = document.getElementById('detail-modal');
const modalBody = document.getElementById('modal-body');
const modalClose = document.getElementById('modal-close');

let currentPage = 1;
let totalPages = 1;

// ==================== 加载数据 ====================
export async function refreshResults() {
  try {
    const data = await api.listResumes({
      page: currentPage,
      pageSize: 50,
      status: statusFilter.value,
      search: searchInput.value.trim(),
    });

    renderTable(data.items);
    resultCountBadge.textContent = data.total;

    totalPages = Math.max(1, Math.ceil(data.total / 50));
    currentPage = data.page;
    updatePagination();
  } catch (e) {
    console.error('加载结果失败:', e);
  }
}

function renderTable(items) {
  if (items.length === 0) {
    resultsBody.innerHTML = `
      <tr class="empty-row">
        <td colspan="9">
          <div class="empty-state">
            <div class="empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <line x1="3" y1="9" x2="21" y2="9"/>
                <line x1="9" y1="21" x2="9" y2="9"/>
              </svg>
            </div>
            <p>暂无数据</p>
            <span>上传并处理简历后，结果将显示在此处</span>
          </div>
        </td>
      </tr>
    `;
    pagination.style.display = 'none';
    return;
  }

  pagination.style.display = '';

  resultsBody.innerHTML = items.map(r => {
    const data = r.extracted_data || {};
    const statusClass = r.status;
    const statusText = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }[r.status] || r.status;

    return `
      <tr>
        <td title="${escapeHtml(r.original_filename)}">${escapeHtml(truncate(r.original_filename, 30))}</td>
        <td>${escapeHtml(data['姓名'] || '-')}</td>
        <td>${escapeHtml(data['性别'] || '-')}</td>
        <td>${escapeHtml(data['手机号码'] || '-')}</td>
        <td>${escapeHtml(data['最高学历'] || '-')}</td>
        <td>${escapeHtml(data['毕业学校'] || '-')}</td>
        <td>${escapeHtml(data['应聘职位'] || '-')}</td>
        <td><span class="status-tag ${statusClass}">${statusText}</span></td>
        <td>
          <div style="display:flex;gap:6px;">
            ${r.status === 'completed' ? `<button class="btn-text view-detail" data-id="${r.id}">详情</button>` : ''}
            ${r.status === 'failed' ? `<button class="btn-text retry-resume" data-id="${r.id}" style="color:var(--accent)">重试</button>` : ''}
            <button class="btn-text delete-resume" data-id="${r.id}" style="color:var(--danger)">删除</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // 事件绑定
  resultsBody.querySelectorAll('.view-detail').forEach(btn => {
    btn.addEventListener('click', () => showDetail(parseInt(btn.dataset.id)));
  });
  resultsBody.querySelectorAll('.retry-resume').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await api.retryResume(parseInt(btn.dataset.id));
        showToast('已加入重试队列', 'success');
        refreshResults();
      } catch (e) {
        showToast(`重试失败: ${e.message}`, 'error');
      }
    });
  });
  resultsBody.querySelectorAll('.delete-resume').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!(await showConfirm('确定删除这条记录吗？'))) return;
      try {
        await api.deleteResume(parseInt(btn.dataset.id));
        showToast('已删除', 'success');
        refreshResults();
      } catch (e) {
        showToast(`删除失败: ${e.message}`, 'error');
      }
    });
  });
}

async function showDetail(id) {
  const [result, fieldsRes] = await Promise.all([
    api.listResumes({ page: 1, pageSize: 50 }),
    fetch('/api/settings/fields').then(r => r.json()).catch(() => []),
  ]);

  const r = result.items.find(item => item.id === id);
  if (!r) return;

  const data = r.extracted_data || {};

  // 使用用户自定义字段，如果没有则用默认字段
  let fields;
  if (fieldsRes.length > 0) {
    fields = fieldsRes.map(f => [f.field_label || f.field_key, data[f.field_key]]);
  } else {
    fields = [
      ['姓名', data['姓名']],
      ['性别', data['性别']],
      ['出生年月', data['出生年月']],
      ['手机号码', data['手机号码']],
      ['最高学历', data['最高学历']],
      ['毕业学校', data['毕业学校']],
      ['毕业年份', data['毕业年份']],
      ['地区', data['地区']],
      ['专业名称', data['专业名称']],
      ['应聘职位', data['应聘职位']],
    ];
  }

    modalBody.innerHTML = `
      <div class="detail-grid">
        ${fields.map(([label, val]) => `
          <div class="detail-field">
            <label>${label}</label>
            <span>${escapeHtml(val || '-')}</span>
          </div>
        `).join('')}
        <div class="detail-field full-width">
          <label>文件名</label>
          <span>${escapeHtml(r.original_filename)}</span>
        </div>
      </div>
    `;

  detailModal.style.display = '';
}

function updatePagination() {
  prevPageBtn.disabled = currentPage <= 1;
  nextPageBtn.disabled = currentPage >= totalPages;
  pageInfo.textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页`;
}

// ==================== 事件 ====================
searchInput.addEventListener('input', debounce(() => {
  currentPage = 1;
  refreshResults();
}, 300));

statusFilter.addEventListener('change', () => {
  currentPage = 1;
  refreshResults();
});

exportBtn.addEventListener('click', () => {
  window.open(api.getExportUrl(), '_blank');
});

prevPageBtn.addEventListener('click', () => {
  if (currentPage > 1) {
    currentPage--;
    refreshResults();
  }
});

nextPageBtn.addEventListener('click', () => {
  if (currentPage < totalPages) {
    currentPage++;
    refreshResults();
  }
});

// Modal 关闭
modalClose.addEventListener('click', () => {
  detailModal.style.display = 'none';
});
detailModal.addEventListener('click', (e) => {
  if (e.target === detailModal) detailModal.style.display = 'none';
});

// ==================== 工具函数 ====================
function truncate(str, max) {
  if (str.length <= max) return str;
  return str.slice(0, max) + '...';
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
