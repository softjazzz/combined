<template>
  <div class="qc-dashboard">
    <a-page-header title="质控看板" sub-title="汇总执行与质量指标">
      <template #extra>
        <a-space>
          <a-button :loading="loading" @click="fetchSummary">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
          <a-button type="primary" :loading="exporting" @click="exportSummary">
            <template #icon><DownloadOutlined /></template>
            导出
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <a-row :gutter="16" class="kpi-row">
      <a-col :span="6">
        <a-card size="small"><a-statistic title="病历数" :value="kpis.total_records" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small"><a-statistic title="执行数" :value="kpis.qc_executions" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small"><a-statistic title="平均得分" :value="kpis.avg_qc_score" :precision="1" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small"><a-statistic title="启用规则" :value="kpis.active_rules" /></a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top: 12px;">
      <a-col :span="8">
        <a-card size="small"><a-statistic title="通过" :value="kpis.passed" /></a-card>
      </a-col>
      <a-col :span="8">
        <a-card size="small"><a-statistic title="告警" :value="kpis.warning" /></a-card>
      </a-col>
      <a-col :span="8">
        <a-card size="small"><a-statistic title="失败" :value="kpis.failed" /></a-card>
      </a-col>
    </a-row>

    <div v-if="downloadUrl" class="export-tip">
      导出已生成：
      <a href="javascript:void(0)" @click="openDownload">{{ downloadUrl }}</a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, DownloadOutlined } from '@ant-design/icons-vue'

const loading = ref(false)
const exporting = ref(false)
const kpis = ref<any>({
  total_records: 0,
  active_rules: 0,
  qc_executions: 0,
  avg_qc_score: 0,
  passed: 0,
  warning: 0,
  failed: 0,
})
const downloadUrl = ref<string>('')

const fetchSummary = async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/reports/qc/summary')
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    kpis.value = data.kpis || {}
  } catch (e: any) {
    message.error('加载看板失败: ' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

const exportSummary = async () => {
  exporting.value = true
  try {
    const resp = await fetch('/api/reports/qc/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ record_ids: [] }),
    })
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    downloadUrl.value = data.download_url
    message.success('导出任务已创建')
  } catch (e: any) {
    message.error('导出失败: ' + (e?.message || e))
  } finally {
    exporting.value = false
  }
}

const openDownload = () => {
  if (downloadUrl.value) {
    window.open(downloadUrl.value, '_blank')
  }
}

onMounted(() => {
  fetchSummary()
})
</script>

<style scoped>
.qc-dashboard {
  padding: 16px;
}
.kpi-row { margin-top: 8px; }
.export-tip { margin-top: 16px; }
</style>
