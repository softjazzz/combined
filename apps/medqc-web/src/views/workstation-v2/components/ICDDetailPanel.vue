<template>
  <div class="icd-detail-panel">
    <!-- 空状态 -->
    <div v-if="!selectedCode" class="detail-empty">
      <div class="empty-icon-wrapper">
        <FileSearchOutlined class="empty-icon" />
      </div>
      <h4>选择编码查看详情</h4>
      <p>从左侧列表点击任意编码，<br/>即可在此处查看完整信息</p>
    </div>

    <!-- 已选编码信息 -->
    <div v-else class="detail-content custom-scrollbar">
      <!-- 编码头部 -->
      <div class="detail-header">
        <div class="code-badge" :class="selectedCode.type === 'icd10' ? 'code-badge--blue' : 'code-badge--green'">
          {{ selectedCode.code }}
        </div>
        <div class="code-meta">
          <h3 class="code-title">{{ selectedCode.name }}</h3>
          <a-tag :color="selectedCode.type === 'icd10' ? 'blue' : 'green'" size="small">
            {{ selectedCode.type === 'icd10' ? 'ICD-10 诊断' : 'ICD-9-CM-3 手术' }}
          </a-tag>
        </div>
      </div>

      <!-- 分类路径（面包屑） -->
      <div v-if="selectedCode.category_path?.length" class="detail-section">
        <div class="section-label">
          <ApartmentOutlined />
          分类路径
        </div>
        <div class="breadcrumb-path">
          <span
            v-for="(item, index) in selectedCode.category_path"
            :key="index"
            class="breadcrumb-item"
          >
            <span class="breadcrumb-text">{{ item }}</span>
            <RightOutlined v-if="index < selectedCode.category_path.length - 1" class="breadcrumb-sep" />
          </span>
        </div>
      </div>

      <!-- 版本映射对照 -->
      <div v-if="selectedCode.mapped_code" class="detail-section">
        <div class="section-label">
          <SwapOutlined />
          版本对照
        </div>
        <div class="mapping-card" :class="{ 'mapping-diff': selectedCode.is_diff }">
          <div class="mapping-row">
            <span class="mapping-from-label">当前版本</span>
            <span class="mapping-arrow">→</span>
            <span class="mapping-to-label">{{ selectedCode.mapped_version }}</span>
          </div>
          <div class="mapping-row">
            <span class="mapping-from-code">{{ selectedCode.code }}</span>
            <span class="mapping-arrow">→</span>
            <span class="mapping-to-code">{{ selectedCode.mapped_code }}</span>
          </div>
          <div v-if="selectedCode.is_diff && selectedCode.mapped_name" class="mapping-diff-name">
            <WarningOutlined style="color: #d46b08" />
            <span>{{ selectedCode.mapped_name }}</span>
          </div>
          <a-tag
            :color="selectedCode.is_diff ? 'orange' : 'green'"
            size="small"
            style="margin-top: 8px"
          >
            {{ selectedCode.is_diff ? '⚠ 编码不同' : '✓ 编码相同' }}
          </a-tag>
        </div>
      </div>

      <!-- 包含说明 -->
      <div v-if="selectedCode.inclusions?.length" class="detail-section">
        <div class="section-label">
          <CheckCircleOutlined style="color: #00A651" />
          包含
        </div>
        <ul class="inclusion-list">
          <li v-for="(item, i) in selectedCode.inclusions" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- 排除说明 -->
      <div v-if="selectedCode.exclusions?.length" class="detail-section">
        <div class="section-label">
          <CloseCircleOutlined style="color: #FF3B30" />
          排除
        </div>
        <ul class="exclusion-list">
          <li v-for="(item, i) in selectedCode.exclusions" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- 操作按钮 -->
      <div class="detail-actions">
        <a-button type="primary" block @click="$emit('copy', selectedCode.code)">
          <template #icon><CopyOutlined /></template>
          复制编码
        </a-button>
        <a-button v-if="allowApply" block style="margin-top: 8px" @click="$emit('apply', selectedCode)">
          <template #icon><CheckCircleOutlined /></template>
          {{ applyLabel || '回填当前字段' }}
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  FileSearchOutlined,
  ApartmentOutlined,
  RightOutlined,
  SwapOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'

export interface ICDCodeDetail {
  code: string
  name: string
  type: 'icd10' | 'icd9cm3'
  category_path?: string[]
  mapped_code?: string
  mapped_name?: string
  mapped_version?: string
  is_diff?: boolean
  inclusions?: string[]
  exclusions?: string[]
}

defineProps<{
  selectedCode: ICDCodeDetail | null
  allowApply?: boolean
  applyLabel?: string
}>()

defineEmits<{
  copy: [code: string]
  apply: [detail: ICDCodeDetail]
}>()
</script>

<style scoped>
.icd-detail-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
}

.empty-icon-wrapper {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0f7ff, #e8f1fd);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-icon {
  font-size: 32px;
  color: #0066CC;
  opacity: 0.6;
}

.detail-empty h4 {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px;
}

.detail-empty p {
  font-size: 13px;
  color: #999;
  margin: 0;
  line-height: 1.6;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f5f5f5;
}

.code-badge {
  font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;
  font-size: 16px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 8px;
  white-space: nowrap;
  letter-spacing: 0.5px;
}
.code-badge--blue {
  background: linear-gradient(135deg, #e8f4ff, #d6ebff);
  color: #0050A0;
  border: 1px solid rgba(0, 102, 204, 0.15);
}
.code-badge--green {
  background: linear-gradient(135deg, #e8f8ee, #d6f0e0);
  color: #006630;
  border: 1px solid rgba(0, 166, 81, 0.15);
}

.code-meta {
  flex: 1;
  min-width: 0;
}

.code-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 6px;
  line-height: 1.4;
}

.detail-section {
  margin-bottom: 16px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

.breadcrumb-path {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}

.breadcrumb-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.breadcrumb-text {
  font-size: 12px;
  color: #555;
}

.breadcrumb-sep {
  font-size: 10px;
  color: #ccc;
}

.mapping-card {
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}
.mapping-card.mapping-diff {
  background: #fffbf0;
  border-color: rgba(212, 107, 8, 0.15);
}

.mapping-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.mapping-from-label, .mapping-to-label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.mapping-arrow {
  color: #ccc;
  font-size: 12px;
}

.mapping-from-code, .mapping-to-code {
  font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.mapping-diff-name {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #d46b08;
}

.inclusion-list, .exclusion-list {
  margin: 0;
  padding: 10px 12px 10px 28px;
  border-radius: 8px;
  list-style-type: disc;
  font-size: 13px;
  line-height: 1.8;
  color: #444;
}

.inclusion-list {
  background: #f6fff9;
  border: 1px solid rgba(0, 166, 81, 0.1);
}
.inclusion-list li::marker {
  color: #00A651;
}

.exclusion-list {
  background: #fff5f5;
  border: 1px solid rgba(255, 59, 48, 0.1);
}
.exclusion-list li::marker {
  color: #FF3B30;
}

.detail-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f5f5f5;
}

/* 滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e0e0e0;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #ccc;
}
</style>
