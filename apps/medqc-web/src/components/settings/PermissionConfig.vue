<template>
  <div class="ds-root">
    <!-- ══════════ Section: 权限矩阵 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">权限配置</h2>
        <p class="ds-section-desc">
          通过权限矩阵控制各角色对系统资源的访问。勾选或取消勾选即时生效。
        </p>
        <div class="pm-legend">
          <div class="pm-legend__item">
            <span class="pm-legend__check pm-legend__check--on">✓</span>
            <span>已授权</span>
          </div>
          <div class="pm-legend__item">
            <span class="pm-legend__check pm-legend__check--off">-</span>
            <span>未授权</span>
          </div>
        </div>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <!-- 矩阵表头 -->
          <div class="pm-header">
            <div class="pm-cell pm-cell--resource">资源/功能</div>
            <div class="pm-cell pm-cell--role" v-for="role in roleColumns" :key="role.key">
              {{ role.title }}
            </div>
          </div>
          <!-- 矩阵行 -->
          <div class="ds-divide">
            <div
              v-for="row in permissionMatrix"
              :key="row.resource"
              class="pm-row"
            >
              <div class="pm-cell pm-cell--resource">
                <span class="pm-resource-name">{{ row.resource }}</span>
              </div>
              <div
                v-for="role in roleColumns"
                :key="role.key"
                class="pm-cell pm-cell--role"
              >
                <label class="pm-checkbox">
                  <input
                    type="checkbox"
                    :checked="row[role.key]"
                    @change="handlePermissionChange(row.resource, role.key, ($event.target as HTMLInputElement).checked)"
                  />
                  <span class="pm-checkbox__visual">
                    {{ row[role.key] ? '✓' : '' }}
                  </span>
                </label>
              </div>
            </div>
          </div>
          <div class="ds-card__footer">
            <span class="ds-row__hint">共 {{ permissionMatrix.length }} 项资源</span>
            <button class="ds-btn ds-btn--primary">保存权限</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import '@/styles/settings-design-system.css'

const roleColumns = [
  { key: 'admin', title: '管理员' },
  { key: 'qc_manager', title: '质控管理员' },
  { key: 'qc_staff', title: '质控人员' },
  { key: 'doctor', title: '医务人员' },
]

const permissionMatrix = ref([
  { resource: '仪表板', admin: true, qc_manager: true, qc_staff: true, doctor: true },
  { resource: '质控工作站', admin: true, qc_manager: true, qc_staff: true, doctor: false },
  { resource: '质控规则管理', admin: true, qc_manager: true, qc_staff: false, doctor: false },
  { resource: '任务管理', admin: true, qc_manager: true, qc_staff: true, doctor: false },
  { resource: '统计分析', admin: true, qc_manager: true, qc_staff: true, doctor: true },
  { resource: '用户管理', admin: true, qc_manager: false, qc_staff: false, doctor: false },
  { resource: '角色管理', admin: true, qc_manager: false, qc_staff: false, doctor: false },
  { resource: '系统配置', admin: true, qc_manager: false, qc_staff: false, doctor: false },
  { resource: 'LLM 配置', admin: true, qc_manager: true, qc_staff: false, doctor: false },
  { resource: '数据同步', admin: true, qc_manager: true, qc_staff: false, doctor: false },
])

const handlePermissionChange = (resource: string, role: string, checked: boolean) => {
  const row = permissionMatrix.value.find(r => r.resource === resource)
  if (row) {
    ;(row as any)[role] = checked
  }
  message.info(`${resource} - ${role}: ${checked ? '授权' : '取消授权'}`)
}
</script>

<style scoped>
/* 矩阵表头 */
.pm-header {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* 矩阵行 */
.pm-row {
  display: flex;
  align-items: center;
  padding: 8px 20px;
  transition: background 0.12s;
}
.pm-row:hover { background: rgba(248, 250, 252, 0.7); }

/* 单元格 */
.pm-cell {
  display: flex;
  align-items: center;
  justify-content: center;
}
.pm-cell--resource {
  flex: 1;
  justify-content: flex-start;
  min-width: 120px;
}
.pm-cell--role {
  width: 90px;
  flex-shrink: 0;
}

.pm-resource-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

/* 自定义 Checkbox */
.pm-checkbox {
  position: relative;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pm-checkbox input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.pm-checkbox__visual {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1.5px solid #d1d5db;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  transition: all 0.15s ease;
}
.pm-checkbox input:checked + .pm-checkbox__visual {
  background: #2563eb;
  border-color: #2563eb;
  box-shadow: 0 1px 4px rgba(37, 99, 235, 0.25);
}
.pm-checkbox:hover .pm-checkbox__visual {
  border-color: #2563eb;
}

/* 左侧图例 */
.pm-legend {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pm-legend__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}
.pm-legend__check {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}
.pm-legend__check--on {
  background: #2563eb;
  color: #fff;
}
.pm-legend__check--off {
  background: #f1f5f9;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
}
</style>
