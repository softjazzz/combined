<!--
  空态提示组件
  用于 LLMQCDemoEnhanced 页面，在无质控结果时显示友好提示
-->
<template>
  <div class="empty-result-state">
    <a-empty
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
      :image-style="{ height: '120px' }"
    >
      <template #description>
        <div class="empty-description">
          <h3 class="empty-title">尚未产出质控结果</h3>
          <p class="empty-text">
            点击"开始分析"执行质控分析，或返回前一步补充测试对象和规则配置
          </p>
        </div>
      </template>
      
      <template #default>
        <a-space :size="12" class="empty-actions">
          <a-button 
            type="primary" 
            size="large"
            @click="$emit('start-analysis')"
          >
            <PlayCircleOutlined />
            开始分析
          </a-button>
          <a-button 
            size="large"
            @click="$emit('go-back')"
          >
            <LeftOutlined />
            返回上一步
          </a-button>
        </a-space>
      </template>
    </a-empty>
    
    <!-- 提示卡片 -->
    <a-card 
      class="tips-card" 
      size="small"
      :bordered="false"
    >
      <template #title>
        <BulbOutlined class="tips-icon" />
        <span>操作提示</span>
      </template>
      
      <ul class="tips-list">
        <li>
          <CheckCircleOutlined class="tip-icon success" />
          确保已在"测试对象"步骤选择病历和文书
        </li>
        <li>
          <CheckCircleOutlined class="tip-icon success" />
          确保已在"规则配置"步骤选择至少一条质控规则
        </li>
        <li>
          <InfoCircleOutlined class="tip-icon info" />
          点击"开始分析"后，系统将自动执行质控分析
        </li>
        <li>
          <InfoCircleOutlined class="tip-icon info" />
          分析完成后，将在此处显示质控结果总览和违规详情
        </li>
      </ul>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { Empty } from 'ant-design-vue'
import { 
  PlayCircleOutlined, 
  LeftOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'

/**
 * 组件事件
 */
defineEmits<{
  'start-analysis': []
  'go-back': []
}>()
</script>

<style scoped>
.empty-result-state {
  padding: 40px 20px;
  text-align: center;
}

.empty-description {
  margin-bottom: 24px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 14px;
  color: #8c8c8c;
  line-height: 1.6;
  margin: 0;
}

.empty-actions {
  margin-top: 24px;
}

.tips-card {
  max-width: 600px;
  margin: 32px auto 0;
  background-color: #fafafa;
  border-radius: 8px;
}

.tips-card :deep(.ant-card-head) {
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.tips-card :deep(.ant-card-head-title) {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.tips-icon {
  color: #faad14;
  font-size: 16px;
}

.tips-list {
  list-style: none;
  padding: 0;
  margin: 0;
  text-align: left;
}

.tips-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 0;
  font-size: 14px;
  color: #595959;
  line-height: 1.6;
}

.tip-icon {
  flex-shrink: 0;
  margin-top: 2px;
  font-size: 14px;
}

.tip-icon.success {
  color: #52c41a;
}

.tip-icon.info {
  color: #1890ff;
}
</style>

