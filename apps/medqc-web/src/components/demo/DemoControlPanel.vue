<template>
  <div class="demo-control-panel">
    <a-row
      :gutter="16"
      align="middle"
      justify="space-between"
      class="control-row"
    >
      <!-- 左侧：演示控制按钮 -->
      <a-col :flex="1">
        <a-space
          :size="12"
          wrap
          class="control-left"
        >
          <a-select
            :value="demoStore.currentStep"
            style="width: 180px"
            size="middle"
            @change="handleStepChange"
          >
            <a-select-option value="target">
              <FileSearchOutlined />
              测试对象选择
            </a-select-option>
            <a-select-option value="rules">
              <SettingOutlined />
              规则配置
            </a-select-option>
            <a-select-option value="run">
              <ThunderboltOutlined />
              运行与结果
            </a-select-option>
          </a-select>
        </a-space>
      </a-col>

      <!-- 右侧：进度显示 + 快捷操作 -->
      <a-col :flex="'none'">
        <a-space :size="16">
          <!-- 进度显示 -->
          <a-tooltip title="当前进度">
            <a-progress
              type="circle"
              :percent="demoStore.progress"
              :width="40"
              :stroke-width="8"
              :status="demoStore.error ? 'exception' : 'normal'"
            />
          </a-tooltip>

          <!-- 快捷操作菜单 -->
          <a-dropdown>
            <a-button :icon="h(MoreOutlined)">
              更多
            </a-button>
            <template #overlay>
              <a-menu @click="handleMenuClick">
                <a-menu-item key="import">
                  <ImportOutlined />
                  导入演示状态
                </a-menu-item>
                <a-menu-item key="export">
                  <ExportOutlined />
                  导出演示状态
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="config">
                  <SettingOutlined />
                  演示配置
                </a-menu-item>
                <a-menu-item
                  key="clear"
                  danger
                >
                  <DeleteOutlined />
                  清除状态
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-space>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { message } from 'ant-design-vue'
import { openConfirmDialog } from '@/views/workstation-v4/utils/confirmDialog'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import { useQCDemoStore } from '@/stores/qcDemo'
import {
  MoreOutlined,
  ImportOutlined,
  ExportOutlined,
  SettingOutlined,
  DeleteOutlined,
  FileSearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import './DemoControlPanel.less'

const demoStore = useQCDemoStore()

// 事件处理
const handleStepChange = async (step: string) => {
  console.log('[DemoControlPanel] 步骤选择器变化:', step, '当前步骤:', demoStore.currentStep)
  await demoStore.jumpToStep(step as 'target' | 'rules' | 'run')
  console.log('[DemoControlPanel] 跳转完成，新步骤:', demoStore.currentStep)
}

const handleMenuClick = async ({ key }: MenuInfo) => {
  const keyStr = String(key)
  switch (keyStr) {
    case 'import':
      handleImport()
      break
    case 'export':
      handleExport()
      break
    case 'config':
      handleConfig()
      break
    case 'clear':
      handleClear()
      break
  }
}

const handleImport = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const data = JSON.parse(text)
      await demoStore.importDemoState(data)
      message.success('演示状态导入成功')
    } catch (error) {
      console.error('导入失败:', error)
      message.error('导入失败，请检查文件格式')
    }
  }
  input.click()
}

const handleExport = () => {
  try {
    const data = demoStore.exportDemoState()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `qc-demo-state-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('演示状态导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    message.error('导出失败')
  }
}

const handleConfig = () => {
  message.info('演示配置功能开发中...')
  // TODO: 打开配置模态框
}

const handleClear = () => {
  openConfirmDialog({
    title: '确认清除所有状态？',
    content: '此操作将清除所有演示数据和进度，无法恢复',
    okText: '确认清除',
    cancelText: '取消',
    okType: 'danger',
    onOk: () => {
      localStorage.removeItem('qc-demo-state')
      demoStore.$reset()
      message.success('状态已清除')
    },
  })
}
</script>
