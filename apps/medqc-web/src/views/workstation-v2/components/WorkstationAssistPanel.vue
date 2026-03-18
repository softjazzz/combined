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
      <span class="assist-trigger__text">&#x5206;&#x6790;&#x9762;&#x677F;</span>
      <span v-if="totalBadgeCount > 0" class="assist-trigger__badge">{{ totalBadgeCount }}</span>
    </button>

    <Transition name="assist-slide">
      <section v-if="mergedVisible" class="assist-panel">
        <header class="assist-panel__header">
          <div class="assist-panel__title-wrap">
            <RobotOutlined class="assist-panel__title-icon" />
            <div>
              <div class="assist-panel__title">&#x667A;&#x80FD;&#x5206;&#x6790;&#x9762;&#x677F;</div>
            </div>
          </div>
          <div class="assist-panel__actions">
            <a-button
              type="text"
              size="small"
              class="assist-panel__action-btn"
              @click="$emit('refresh-tab', currentTab)"
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
          <div class="assist-panel__patient-strip">
            <div class="assist-panel__patient-avatar">
              {{ (patientInfo.name || '?').charAt(0) }}
            </div>
            <div class="assist-panel__patient-info">
              <div class="assist-panel__patient-name-line">
                <span class="assist-panel__patient-name">{{ patientInfo.name || '\u672A\u547D\u540D\u60A3\u8005' }}</span>
                <span class="assist-panel__patient-meta">
                  {{ patientInfo.sex || '-' }}
                  <span class="assist-panel__meta-sep">&#x00B7;</span>
                  {{ patientInfo.age || '-' }}
                </span>
              </div>
              <div v-if="patientInfo.visitId" class="assist-panel__patient-id">
                <span class="assist-panel__patient-id-label">&#x4F4F;&#x9662;&#x53F7;</span>
                <span class="assist-panel__patient-id-value">{{ patientInfo.visitId }}</span>
              </div>
            </div>
            <div v-if="totalBadgeCount > 0" class="assist-panel__summary">
              <span class="assist-panel__summary-label">&#x5F85;&#x5904;&#x7406;</span>
              <strong class="assist-panel__summary-value">{{ totalBadgeCount }}</strong>
            </div>
          </div>
          <div class="assist-panel__patient-diagnosis" :title="patientInfo.diagnosis || ''">
            <span class="assist-panel__patient-diag-pulse"><span></span></span>
            {{ patientInfo.diagnosis || '\u6682\u65E0\u4E3B\u8BCA\u65AD\u4FE1\u606F\uFF0C\u5EFA\u8BAE\u901A\u8FC7 AI \u63D0\u53D6' }}
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
              <span class="assist-sidebar__icon">
                <component :is="tab.icon" />
              </span>
              <span class="assist-sidebar__label">{{ tab.label }}</span>
              <span v-if="getBadge(tab.key) > 0" class="assist-sidebar__badge">{{ getBadge(tab.key) }}</span>
            </button>
          </nav>

          <div class="assist-panel__content">
            <div v-if="currentTab === 'content'" class="assist-panel__slot">
              <slot name="content">
                <div class="assist-empty">
                  <SafetyCertificateOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">&#x5185;&#x6DB5;&#x8D28;&#x63A7;&#x5F85;&#x63A5;&#x5165;</div>
                </div>
              </slot>
            </div>

            <div v-else-if="currentTab === 'form' || currentTab === 'coding' || currentTab === 'cost'" class="assist-panel__slot">
              <slot name="qc" :active-sub-tab="currentTab">
                <div class="assist-empty">
                  <CheckCircleOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">&#x8D28;&#x63A7;&#x9762;&#x677F;&#x5F85;&#x63A5;&#x5165;</div>
                </div>
              </slot>
            </div>

            <div v-else-if="currentTab === 'profile'" class="assist-panel__slot">
              <slot name="profile">
                <div class="assist-empty">
                  <RobotOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">AI &#x753B;&#x50CF;&#x5F85;&#x63A5;&#x5165;</div>
                </div>
              </slot>
            </div>

            <div v-else-if="currentTab === 'drg'" class="assist-panel__slot">
              <slot name="drg">
                <div class="assist-empty">
                  <NodeIndexOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">DRG &#x9762;&#x677F;&#x5F85;&#x63A5;&#x5165;</div>
                </div>
              </slot>
            </div>

            <div v-else class="assist-panel__slot">
              <slot name="message">
                <div class="assist-empty">
                  <NotificationOutlined class="assist-empty__icon" />
                  <div class="assist-empty__title">&#x6D88;&#x606F;&#x6982;&#x89C8;&#x5F85;&#x63A5;&#x5165;</div>
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
  CodeOutlined,
  DollarOutlined,
  FileTextOutlined,
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
  (e: 'refresh-tab', tab: AssistTabKey): void
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
  { key: 'content' as const, label: '\u5185\u6DB5\n\u8D28\u63A7', icon: SafetyCertificateOutlined },
  { key: 'form' as const, label: '\u9996\u9875\n\u8D28\u63A7', icon: FileTextOutlined },
  { key: 'coding' as const, label: '\u7F16\u7801\n\u8D28\u63A7', icon: CodeOutlined },
  { key: 'cost' as const, label: '\u63A7\u8D39\n\u76D1\u6D4B', icon: DollarOutlined },
  { key: 'profile' as const, label: 'AI\n\u753B\u50CF', icon: RobotOutlined },
  { key: 'drg' as const, label: 'DRG', icon: NodeIndexOutlined },
  { key: 'message' as const, label: '\u6D88\u606F', icon: NotificationOutlined },
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
  right: 18px;
  bottom: 18px;
  z-index: 60;
}

.assist-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 999px;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.98), rgba(29, 78, 216, 0.98)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0));
  color: #fff;
  padding: 10px 14px;
  box-shadow:
    0 14px 30px rgba(29, 78, 216, 0.26),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.assist-trigger:hover {
  transform: translateY(-1px);
  box-shadow:
    0 18px 34px rgba(29, 78, 216, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.assist-trigger__icon {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.16);
}

.assist-trigger__text {
  font-size: 12px;
  font-weight: 700;
}

.assist-trigger__badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  line-height: 18px;
  text-align: center;
  font-weight: 700;
}

.assist-panel {
  width: 404px;
  height: min(700px, calc(100vh - 36px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 22px;
  background: linear-gradient(180deg, #f5f9ff 0%, #edf4ff 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  box-shadow:
    0 26px 60px rgba(15, 23, 42, 0.18),
    0 8px 20px rgba(37, 99, 235, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.assist-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 12px 10px;
  background:
    linear-gradient(135deg, #2563eb 0%, #1d4ed8 72%, #1e40af 100%);
  border-bottom: 1px solid rgba(37, 99, 235, 0.28);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    0 8px 18px rgba(37, 99, 235, 0.18);
}

.assist-panel__title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.assist-panel__title-icon {
  color: rgba(255, 255, 255, 0.96);
  font-size: 16px;
  margin-top: 2px;
  filter: drop-shadow(0 2px 4px rgba(15, 23, 42, 0.18));
}

.assist-panel__title {
  color: #ffffff;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.assist-panel__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.assist-panel__action-btn {
  color: rgba(255, 255, 255, 0.88);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.assist-panel__action-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.2);
}

.assist-panel__patient {
  padding: 10px 12px 10px;
  background: linear-gradient(180deg, rgba(242, 247, 255, 0.96), rgba(247, 250, 255, 0.88));
  border-bottom: 1px solid rgba(203, 213, 225, 0.72);
  display: grid;
  gap: 8px;
}

.assist-panel__patient-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(191, 219, 254, 0.8);
  box-shadow:
    0 10px 24px rgba(37, 99, 235, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.assist-panel__patient-avatar {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: #1d4ed8;
  font-size: 15px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid rgba(147, 197, 253, 0.48);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.assist-panel__patient-info {
  min-width: 0;
  flex: 1;
}

.assist-panel__patient-name-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
  flex-wrap: wrap;
}

.assist-panel__patient-name {
  font-size: 12px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.assist-panel__patient-meta {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.assist-panel__meta-sep {
  margin: 0 2px;
  color: #cbd5e1;
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
  font-size: 10px;
  color: #334155;
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  font-weight: 600;
  background: linear-gradient(180deg, #f8fbff, #edf4ff);
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(226, 232, 240, 0.7);
}

.assist-panel__patient-diagnosis {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 999px;
  padding: 7px 10px;
  border: 1px solid rgba(226, 232, 240, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.assist-panel__patient-diag-pulse {
  position: relative;
  display: inline-flex;
  width: 8px;
  height: 8px;
  flex-shrink: 0;
}

.assist-panel__patient-diag-pulse > span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}

.assist-panel__summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  padding: 5px 9px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2563eb, #1d4ed8);
  border: 1px solid rgba(37, 99, 235, 0.92);
  flex-shrink: 0;
  box-shadow:
    0 8px 18px rgba(37, 99, 235, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.assist-panel__summary-label {
  font-size: 10px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.76);
}

.assist-panel__summary-value {
  font-size: 12px;
  line-height: 1;
  font-weight: 800;
  color: #ffffff;
}

.assist-panel__main {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.assist-sidebar {
  width: 68px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, #2563eb 0%, #1d4ed8 56%, #1e40af 100%);
  border-right: 1px solid rgba(37, 99, 235, 0.42);
  overflow-y: auto;
  padding: 10px 6px;
  gap: 6px;
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.08);
}

.assist-sidebar__item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 64px;
  padding: 10px 6px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.76);
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
  line-height: 1.2;
  text-align: center;
  white-space: pre-line;
  border-radius: 16px;
}

.assist-sidebar__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  font-size: 13px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.assist-sidebar__item:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.assist-sidebar__item--active {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.96));
  color: #1d4ed8;
  border: 1px solid rgba(191, 219, 254, 0.88);
  box-shadow:
    0 14px 24px rgba(15, 23, 42, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.78);
}

.assist-sidebar__item--active .assist-sidebar__icon {
  background: linear-gradient(180deg, #eff6ff, #dbeafe);
  color: #1d4ed8;
  box-shadow:
    0 6px 14px rgba(59, 130, 246, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.78);
}

.assist-sidebar__item--active::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 34px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 0 12px rgba(255, 255, 255, 0.45);
}

.assist-sidebar__label {
  pointer-events: none;
  letter-spacing: 0.01em;
  word-break: break-word;
  max-width: 42px;
}

.assist-sidebar__badge {
  position: absolute;
  top: 6px;
  right: 6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: #ffffff;
  color: #1d4ed8;
  font-size: 9px;
  line-height: 16px;
  text-align: center;
  font-weight: 800;
  border: 2px solid rgba(37, 99, 235, 0.18);
}

.assist-panel__content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background:
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.1), transparent 28%),
    linear-gradient(180deg, rgba(251, 253, 255, 0.96), rgba(244, 248, 255, 0.98));
}

.assist-panel__slot {
  min-height: 100%;
  padding: 12px 12px 14px;
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
  color: #93a8c2;
  margin-bottom: 12px;
}

.assist-empty__title {
  font-size: 14px;
  font-weight: 700;
  color: #2f3f57;
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

@media (max-width: 640px) {
  .assist-wrapper {
    right: 12px;
    bottom: 12px;
  }

  .assist-panel {
    width: min(392px, calc(100vw - 24px));
    height: min(680px, calc(100vh - 24px));
  }
}
</style>
