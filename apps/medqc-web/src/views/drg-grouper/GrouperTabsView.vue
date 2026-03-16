<template>
  <div class="grouper-page">
    <!-- 页面标题 + Tab 切换 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <ForkOutlined class="title-icon" />
          医保分组器
        </h1>
      </div>
      <a-tabs v-model:activeKey="activeTab" class="header-tabs" @change="onTabChange">
        <a-tab-pane key="drg">
          <template #tab>
            <span class="tab-label">
              <ForkOutlined />
              DRG 分组
              <a-tag color="blue" class="tab-tag">CHS-DRG 2.0</a-tag>
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="dip">
          <template #tab>
            <span class="tab-label">
              <ApartmentOutlined />
              DIP 分组
              <a-tag color="green" class="tab-tag">四川 DIP</a-tag>
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 内容区域 -->
    <div class="tab-content">
      <DrgGrouperView v-if="activeTab === 'drg'" :embedded="true" />
      <DipGrouperView v-else-if="activeTab === 'dip'" :embedded="true" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ForkOutlined, ApartmentOutlined } from '@ant-design/icons-vue'
import DrgGrouperView from './DrgGrouperView.vue'
import DipGrouperView from './DipGrouperView.vue'

const activeTab = ref('drg')

function onTabChange(_key: string) {
  // Tab change is handled by v-model
}
</script>

<style scoped>
.grouper-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(135deg, #f0f5ff 0%, #f5f7fa 100%);
}

.page-header {
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
  gap: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  padding: 16px 0;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  white-space: nowrap;
}

.title-icon {
  color: #1890ff;
  margin-right: 8px;
}

.header-tabs {
  margin-bottom: -1px;
}

.header-tabs :deep(.ant-tabs-nav) {
  margin: 0;
}

.header-tabs :deep(.ant-tabs-nav::before) {
  border: none;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
}

.tab-tag {
  font-size: 11px;
  line-height: 18px;
  padding: 0 6px;
  margin: 0;
}

.tab-content {
  flex: 1;
  overflow: hidden;
}

/* 覆盖子组件的页面头部，使用容器的头部 */
.tab-content :deep(.drg-grouper-page),
.tab-content :deep(.dip-grouper-page) {
  height: 100%;
}

.tab-content :deep(.drg-grouper-page > .page-header),
.tab-content :deep(.dip-grouper-page > .page-header) {
  display: none;
}
</style>
