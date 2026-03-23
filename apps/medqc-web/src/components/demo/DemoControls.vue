<template>
  <div class="demo-controls">
    <a-space wrap>
      <!-- 主要操作按钮 -->
      <a-button
        type="primary"
        :loading="isRunning"
        :disabled="!canStart"
        @click="$emit('start')"
      >
        <PlayCircleOutlined />
        {{ isRunning ? '分析进行中' : '开始分析' }}
      </a-button>

      <a-button
        v-if="isRunning"
        @click="$emit('toggle-pause')"
      >
        <PauseCircleOutlined v-if="!isPaused" />
        <PlayCircleOutlined v-else />
        {{ isPaused ? '继续' : '暂停' }}
      </a-button>

      <a-button
        v-if="isRunning"
        danger
        @click="$emit('stop')"
      >
        <StopOutlined />
        停止
      </a-button>

      <a-button @click="$emit('replay')">
        <ReloadOutlined />
        重播
      </a-button>

      <a-divider type="vertical" />

      <!-- 步骤导航 -->
      <a-button
        :icon="h(LeftOutlined)"
        :disabled="currentStep === 'target'"
        size="small"
        @click="$emit('previous-step')"
      >
        上一步
      </a-button>

      <a-select
        :value="currentStep"
        style="width: 120px"
        size="small"
        @change="(value: string) => $emit('jump-step', value)"
      >
        <a-select-option value="target">
          测试对象
        </a-select-option>
        <a-select-option value="rules">
          规则配置
        </a-select-option>
        <a-select-option value="run">
          运行与结果
        </a-select-option>
      </a-select>

      <a-button
        :icon="h(RightOutlined)"
        :disabled="currentStep === 'run'"
        size="small"
        @click="$emit('next-step')"
      >
        下一步
      </a-button>

      <a-divider type="vertical" />

      <!-- 更多操作 -->
      <a-dropdown>
        <template #overlay>
          <a-menu @click="handleMenuAction">
            <a-menu-item key="export">
              <DownloadOutlined />
              导出演示数据
            </a-menu-item>
            <a-menu-item key="import">
              <UploadOutlined />
              导入演示数据
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item key="clear">
              <DeleteOutlined />
              清除演示状态
            </a-menu-item>
            <a-menu-item key="config">
              <SettingOutlined />
              演示配置
            </a-menu-item>
          </a-menu>
        </template>
        <a-button size="small">
          更多
          <DownOutlined />
        </a-button>
      </a-dropdown>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  LeftOutlined,
  RightOutlined,
  DownloadOutlined,
  UploadOutlined,
  DeleteOutlined,
  SettingOutlined,
  DownOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  isRunning: boolean
  isPaused: boolean
  canStart: boolean
  currentStep: 'target' | 'rules' | 'run'
}

defineProps<Props>()

// Emits
const emit = defineEmits<{
  start: []
  'toggle-pause': []
  stop: []
  replay: []
  'previous-step': []
  'next-step': []
  'jump-step': [step: string]
  'menu-action': [action: string]
}>()

// 处理菜单操作
const handleMenuAction = ({ key }: { key: string }) => {
  emit('menu-action', key)
}
</script>

<style scoped lang="less">
.demo-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
