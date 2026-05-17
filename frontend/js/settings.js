/**
 * 提取设置面板 — 自定义提取字段管理
 */
import { api } from './api.js';
import { showToast, showConfirm } from './key-manager.js';

const fieldList = document.getElementById('field-list');
const fieldsEmpty = document.getElementById('fields-empty');
const fieldKeyInput = document.getElementById('field-key-input');
const fieldLabelInput = document.getElementById('field-label-input');
const fieldHintInput = document.getElementById('field-hint-input');
const addFieldBtn = document.getElementById('add-field-btn');
const resetFieldsBtn = document.getElementById('reset-fields-btn');

async function loadFields() {
  const res = await fetch('/api/settings/fields');
  return res.json();
}

async function addField(key, label, hint) {
  const res = await fetch('/api/settings/fields', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ field_key: key, field_label: label, field_hint: hint }),
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || '添加失败');
  }
  return res.json();
}

async function deleteField(id) {
  const res = await fetch(`/api/settings/fields/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || '删除失败');
  }
}

async function resetFields() {
  const res = await fetch('/api/settings/fields/reset', { method: 'POST' });
  if (!res.ok) throw new Error('重置失败');
  return res.json();
}

function renderFields(fields) {
  if (fields.length === 0) {
    fieldsEmpty.style.display = '';
    return;
  }
  fieldsEmpty.style.display = 'none';

  fieldList.innerHTML = fields.map((f, i) => `
    <div class="field-item">
      <span class="field-order">${i + 1}</span>
      <div class="field-info">
        <span class="field-key">${esc(f.field_key)}</span>
        <span class="field-label-text">${esc(f.field_label)}</span>
        ${f.field_hint ? `<span class="field-hint-tag">${esc(f.field_hint)}</span>` : ''}
      </div>
      <button class="field-delete-btn" data-id="${f.id}" title="删除">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  `).join('');

  fieldList.querySelectorAll('.field-delete-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await deleteField(parseInt(btn.dataset.id));
        refreshFields();
        showToast('字段已删除', 'success');
      } catch (e) {
        showToast(e.message, 'error');
      }
    });
  });
}

addFieldBtn.addEventListener('click', async () => {
  const key = fieldKeyInput.value.trim();
  const label = fieldLabelInput.value.trim();
  if (!key || !label) {
    showToast('请填写字段名和显示名称', 'error');
    return;
  }
  try {
    await addField(key, label, fieldHintInput.value.trim());
    fieldKeyInput.value = '';
    fieldLabelInput.value = '';
    fieldHintInput.value = '';
    await refreshFields();
    showToast('字段已添加', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
});

resetFieldsBtn.addEventListener('click', async () => {
  if (!(await showConfirm('确定重置为默认提取字段？当前自定义字段将丢失。'))) return;
  try {
    await resetFields();
    await refreshFields();
    showToast('已重置为默认字段', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
});

export async function refreshFields() {
  try {
    const fields = await loadFields();
    renderFields(fields);
  } catch (e) {
    console.error('加载字段失败:', e);
  }
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
