<template>
  <div class="assist-wrapper">
    <button
      v-if="!mergedVisible"
      type="button"
      class="assist-trigger"
      @click="setVisible(true)"
    >
      <span class="assist-trigger__icon">
        <AppstoreOutlined />
      </span>
      <span class="assist-trigger__text">分析面板</span>
      <span v-if="totalBadgeCount > 0" class="assist-trigger__badge">{{ totalBadgeCount }}</span>
    </button>

    <Transition name="assist-slide">
      <section v-if="mergedVisible" class="assist-panel">
        <header class="assist-panel__header">
          <div class="assist-panel__title-wrap">
            <RobotOutlined class="assist-panel__title-icon" />
            <div>
              <div class="assist-panel__title">智能分析面板</div>
              <div class="assist-panel__subtitle">质控、AI画像、DRG、消息统一入口</div>
            </div>
          </div>
          <div class="assist-panel__actions">
            <a-button
              type="text"
              size="small"
              class="assist-panel__action-btn"
              @click="$emit('refresh')"
            >
              <template #icon><ReloadOutlined /></template>
            </a-button>
            <a-button
              type="text"
              size="small"
              class="assist-panel__action-btn"
              @click="setVisible(false)"
            >
              <template #icon><CloseOutlined /></template>
            </a-button>
          </div>
        </header>

        <div v-if="patientInfo" class="assist-panel__patient">
          <div class="assist-panel__patient-row1">
            <div class="assist-panel__patient-avatar">
              {{ (patientInfo.name || '?').charAt(0) }}
            </div>
            <div class="assist-panel__patient-info">
              <div class="assist-panel__patient-name-line">
                <span class="assist-panel__patient-name">{{ patientInfo.name || '未命名患者' }}</span>
                <span class="assist-panel__patient-tag">{{ patientInfo.sex || '-' }}</span>
                <span class="assist-panel__patient-tag">{{ patientInfo.age || '-' }}</span>
              </div>
              <div v-if="patientInfo.visitId" class="assist-panel__patient-id">
                <span class="assist-panel__patient-id-label">住院号</span>
                <span class="assist-panel__patient-id-value">{{ patientInfo.visitId }}</span>
              </div>
            </div>
          </div>
          <div class="assist-panel__patient-diagnosis" :title="patientInfo.diagnosis || ''">
            <span class="assist-panel__patient-diag-dot"></span>
            {{ patientInfo.diagnosis || '暂无诊断信息' }}
          </div>
        </div>

        <div class="assist-panel__main">
          <nav class="assist-sidebar">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              type="button"
              :class="['assist-sidebar__item', { 'assist-sidebar__item--active': currentTab === tab.key }]"
              @click="changeTab(tab.key)"
            >
              <span class="assist-sidebar__label">{{ tab.label }}</span>
              <span v-if="getBadge(tab.key) > 0" class="assist-sidebar__badge">{{ getBadge(tab.key) }}</span>
            </button>
          </nav>

          <div class="assist-panel__content">
            <div v-if="currentTab === 'content'" class="assist-panel__slot">
              <slot name="content">
                <div class="assist-empty">
                  <SafetyCertificateOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">内涵质控待接入</div>
                </div>
              </slot>
            </div>

            <div v-else-if="currentTab === 'form' || currentTab === 'coding' || currentTab === 'cost'" class="assist-panel__slot">
              <slot name="qc" :active-sub-tab="currentTab">
                <div class="assist-empty">
                  <CheckCircleOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">质控面板待接入</div>
                </div>
              </slot>
            </div>

            <div v-else-if="currentTab === 'profile'" class="assist-panel__slot">
              <slot name="profile">
                <div class="assist-empty">
                  <RobotOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">AI画像待接入</div>
                </div>
              </slot>
            </div>

            <div v-else-if="currentTab === 'drg'" class="assist-panel__slot">
              <slot name="drg">
                <div class="assist-empty">
                  <NodeIndexOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">DRG 面板待接入</div>
                </div>
              </slot>
            </div>

            <div v-else class="assist-panel__slot">
              <slot name="message">
                <div class="assist-empty">
                  <NotificationOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">消息概览待接入</div>
                </div>
              </slot>
            </div>
          </div>
        </div>
      </section>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  AppstoreOutlined,
  CheckCircleOutlined,
  CloseOutlined,
  NodeIndexOutlined,
  NotificationOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons-vue'

type AssistTabKey = 'content' | 'form' | 'coding' | 'cost' | 'profile' | 'drg' | 'message'

interface PatientInfo {
  name?: string
  sex?: string
  age?: string
  diagnosis?: string
  visitId?: string
}

const props = withDefaults(defineProps<{
  visible?: boolean
  defaultVisible?: boolean
  defaultTab?: AssistTabKey
  patientInfo?: PatientInfo | null
  contentCount?: number
  qcCount?: number
  codingCount?: number
  costCount?: number
  profileCount?: number
  drgCount?: number
  messageCount?: number
}>(), {
  visible: undefined,
  defaultVisible: false,
  defaultTab: 'content',
  patientInfo: null,
  contentCount: 0,
  qcCount: 0,
  codingCount: 0,
  costCount: 0,
  profileCount: 0,
  drgCount: 0,
  messageCount: 0,
})

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'tab-change', value: AssistTabKey): void
  (e: 'refresh'): void
}>()

const innerVisible = ref(props.defaultVisible)
const currentTab = ref<AssistTabKey>(props.defaultTab)

watch(
  () => props.visible,
  (value) => {
    if (value !== undefined) innerVisible.value = value
  },
  { immediate: true },
)

watch(
  () => props.defaultTab,
  (value) => {
    currentTab.value = value
  },
)

const mergedVisible = computed(() => (
  props.visible === undefined ? innerVisible.value : props.visible
))

const tabs = [
  { key: 'content' as const, label: '内涵\n质控' },
  { key: 'form' as const, label: '首页\n质控' },
  { key: 'coding' as const, label: '编码\n质控' },
  { key: 'cost' as const, label: '控费\n监测' },
  { key: 'profile' as const, label: 'AI\n画像' },
  { key: 'drg' as const, label: 'DRG' },
  { key: 'message' as const, label: '消息' },
]

const totalBadgeCount = computed(() =>
  props.contentCount + props.qcCount + props.codingCount + props.costCount + props.profileCount + props.drgCount + props.messageCount,
)

function getBadge(tab: AssistTabKey): number {
  if (tab === 'content') return props.contentCount
  if (tab === 'form') return props.qcCount
  if (tab === 'coding') return props.codingCount
  if (tab === 'cost') return props.costCount
  if (tab === 'profile') return props.profileCount
  if (tab === 'drg') return props.drgCount
  return props.messageCount
}

function setVisible(value: boolean) {
  innerVisible.value = value
  emit('update:visible', value)
}

function changeTab(tab: AssistTabKey) {
  currentTab.value = tab
  emit('tab-change', tab)
}
</script>

<style scoped>
.assist-wrapper {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 60;
}

.assist-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  padding: 12px 16px;
  box-shadow:
    0 2px 8px rgba(37, 99, 235, 0.25),
    0 8px 24px rgba(37, 99, 235, 0.30),
    0 20px 48px rgba(79, 70, 229, 0.20);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.assist-trigger:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 12px rgba(37, 99, 235, 0.30),
    0 12px 32px rgba(37, 99, 235, 0.35),
    0 24px 56px rgba(79, 70, 229, 0.25);
}

.assist-trigger__icon {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.18);
}

.assist-trigger__text {
  font-size: 13px;
  font-weight: 700;
}

.assist-trigger__badge {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  line-height: 20px;
  text-align: center;
  font-weight: 700;
}

.assist-panel {
  width: 380px;
  height: min(720px, calc(100vh - 48px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 20px;
  background: #fff;
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
}

.assist-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.assist-panel__title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.assist-panel__title-icon {
  color: #2563eb;
  font-size: 18px;
}

.assist-panel__title {
  color: #0f172a;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.2;
}

.assist-panel__subtitle {
  color: #64748b;
  font-size: 11px;
  margin-top: 2px;
}

.assist-panel__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.assist-panel__action-btn {
  color: #475569;
}

.assist-panel__patient {
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.assist-panel__patient-row1 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.assist-panel__patient-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.assist-panel__patient-info {
  min-width: 0;
  flex: 1;
}

.assist-panel__patient-name-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.assist-panel__patient-name {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.02em;
}

.assist-panel__patient-tag {
  font-size: 11px;
  color: #64748b;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.assist-panel__patient-id {
  display: flex;
  align-items: center;
  gap: 6px;
}

.assist-panel__patient-id-label {
  font-size: 10px;
  color: #94a3b8;
  font-weight: 600;
}

.assist-panel__patient-id-value {
  font-size: 12px;
  color: #475569;
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.assist-panel__patient-diagnosis {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px 10px;
}

.assist-panel__patient-diag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

.assist-panel__main {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.assist-sidebar {
  width: 52px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #f1f5f9;
  border-right: 1px solid #e2e8f0;
  overflow-y: auto;
}

.assist-sidebar__item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 14px 4px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-bottom: 1px solid #e2e8f0;
  transition: all 0.15s ease;
  line-height: 1.4;
  text-align: center;
  white-space: pre-line;
}

.assist-sidebar__item:hover {
  background: #e2e8f0;
  color: #334155;
}

.assist-sidebar__item--active {
  background: #fff;
  color: #2563eb;
  font-weight: 800;
  border-right: 1px solid #fff;
  margin-right: -1px;
}

.assist-sidebar__item--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: #2563eb;
}

.assist-sidebar__label {
  pointer-events: none;
}

.assist-sidebar__badge {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 9px;
  line-height: 16px;
  text-align: center;
  font-weight: 700;
}

.assist-panel__content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: #f8fafc;
}

.assist-panel__slot {
  min-height: 100%;
}

.assist-empty {
  min-height: 100%;
  padding: 28px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
}

.assist-empty__icon {
  font-size: 28px;
  color: #94a3b8;
  margin-bottom: 12px;
}

.assist-empty__title {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.assist-slide-enter-active,
.assist-slide-leave-active {
  transition: all 0.2s ease;
}

.assist-slide-enter-from,
.assist-slide-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.98);
}
</style>
