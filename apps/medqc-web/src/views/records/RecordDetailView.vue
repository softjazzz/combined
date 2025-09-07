<template>
  <div class="page-container">
    <div class="page-header">
      <div class="flex items-center gap-4">
        <a-button :icon="h(ArrowLeftOutlined)" @click="goBack">
          返回
        </a-button>
        <h1 class="page-title">病案详情</h1>
      </div>
      
      <a-button type="primary" :icon="h(PlayCircleOutlined)">
        开始质控
      </a-button>
    </div>
    
    <div class="grid grid-cols-12 gap-6">
      <!-- 病案信息 -->
      <div class="col-span-8">
        <a-card title="基本信息" class="mb-6">
          <a-descriptions :column="2" bordered>
            <a-descriptions-item label="病案号">R202312001</a-descriptions-item>
            <a-descriptions-item label="患者姓名">张**</a-descriptions-item>
            <a-descriptions-item label="科室">内科</a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-badge status="success" text="已完成" />
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
        
        <a-card title="病案内容">
          <div class="bg-gray-50 p-4 rounded">
            <p>主诉：胸闷气短3天</p>
            <p>现病史：患者3天前无明显诱因出现胸闷气短...</p>
          </div>
        </a-card>
      </div>
      
      <!-- 操作面板 -->
      <div class="col-span-4">
        <a-card title="快速操作">
          <div class="space-y-3">
            <a-button block :icon="h(EditOutlined)">编辑病案</a-button>
            <a-button block :icon="h(DownloadOutlined)">下载报告</a-button>
            <a-button block danger :icon="h(DeleteOutlined)">删除病案</a-button>
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { useRouter } from 'vue-router'
import { 
  ArrowLeftOutlined,
  PlayCircleOutlined,
  EditOutlined,
  DownloadOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

const router = useRouter()

const goBack = () => {
  router.go(-1)
}
</script>

<style scoped>
.page-container {
  @apply p-6;
}
.page-header {
  @apply flex items-center justify-between mb-6;
}
.page-title {
  @apply text-2xl font-bold text-gray-900;
}
</style>