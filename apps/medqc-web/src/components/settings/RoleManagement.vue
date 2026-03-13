<template>
  <div class="ds-root">
    <!-- ══════════ Section: 角色一览 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">角色管理</h2>
        <p class="ds-section-desc">
          定义系统中的角色及其权限范围。点击角色卡片可查看详情和编辑权限分配。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="rm-role-grid">
          <div
            v-for="role in roles"
            :key="role.key"
            class="ds-card rm-role-card"
            @click="$emit('edit-role', role)"
          >
            <div class="ds-card__body">
              <div class="rm-role-header">
                <div class="rm-role-icon" :style="{ background: role.bgColor }">
                  <component :is="role.icon" :style="{ color: role.color, fontSize: '18px' }" />
                </div>
                <div class="rm-role-meta">
                  <div class="ds-row__label">{{ role.name }}</div>
                  <div class="ds-row__hint">{{ role.description }}</div>
                </div>
              </div>
            </div>
            <div class="ds-card__footer rm-role-footer">
              <div class="rm-stat">
                <span class="rm-stat__num">{{ role.userCount }}</span>
                <span class="rm-stat__label">位用户</span>
              </div>
              <div class="rm-stat">
                <span class="rm-stat__num">{{ role.permissionCount }}</span>
                <span class="rm-stat__label">项权限</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  CrownOutlined,
  SafetyOutlined,
  SafetyCertificateOutlined,
  UserOutlined
} from '@ant-design/icons-vue'
import '@/styles/settings-design-system.css'

defineEmits(['edit-role'])

const roles = ref([
  {
    key: 'admin',
    name: '系统管理员',
    description: '拥有系统全部权限，可以管理用户、角色和系统配置',
    icon: CrownOutlined,
    color: '#FF7A45',
    bgColor: 'rgba(255, 122, 69, 0.1)',
    userCount: 2,
    permissionCount: 25
  },
  {
    key: 'qc_manager',
    name: '质控管理员',
    description: '负责质控规则管理和质控流程监督',
    icon: SafetyOutlined,
    color: '#0B64D4',
    bgColor: 'rgba(11, 100, 212, 0.1)',
    userCount: 5,
    permissionCount: 18
  },
  {
    key: 'qc_staff',
    name: '质控人员',
    description: '执行质控分析和审核工作',
    icon: SafetyCertificateOutlined,
    color: '#52C41A',
    bgColor: 'rgba(82, 196, 26, 0.1)',
    userCount: 12,
    permissionCount: 10
  },
  {
    key: 'doctor',
    name: '医务人员',
    description: '查看质控结果和病案反馈',
    icon: UserOutlined,
    color: '#8E63F7',
    bgColor: 'rgba(142, 99, 247, 0.1)',
    userCount: 48,
    permissionCount: 5
  }
])
</script>

<style scoped>
.rm-role-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 640px) {
  .rm-role-grid { grid-template-columns: 1fr; }
}

.rm-role-card {
  cursor: pointer;
  transition: all 0.15s ease;
}
.rm-role-card:hover {
  border-color: #2563eb;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.12);
  transform: translateY(-1px);
}

.rm-role-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px;
}

.rm-role-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rm-role-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rm-role-footer {
  display: flex;
  gap: 24px;
  padding: 10px 20px !important;
}

.rm-stat {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.rm-stat__num {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.rm-stat__label {
  font-size: 12px;
  color: #94a3b8;
}
</style>
