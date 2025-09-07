<template>
  <AdminLayout>
    <div class="layout-test">
      <h1 class="text-2xl font-bold text-gray-900 mb-6">布局测试页面</h1>
      
      <!-- 测试卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-2">专业医疗风格</h3>
          <p class="text-gray-600">采用简洁、专业的医疗行业UI设计风格</p>
        </div>
        
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-2">标准色彩方案</h3>
          <p class="text-gray-600">使用医疗行业标准色彩，避免花哨效果</p>
        </div>
        
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-2">响应式设计</h3>
          <p class="text-gray-600">支持不同屏幕尺寸的响应式布局</p>
        </div>
      </div>
      
      <!-- 测试表格 -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">数据表格示例</h3>
        <a-table
          :columns="columns"
          :data-source="data"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="record.status === '正常' ? 'green' : 'orange'">
                {{ record.status }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button type="link" size="small">查看</a-button>
                <a-button type="link" size="small">编辑</a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import AdminLayout from '@/components/layout/AdminLayout.vue'

// 表格列配置
const columns = [
  { title: '患者姓名', dataIndex: 'name', key: 'name' },
  { title: '病案号', dataIndex: 'recordId', key: 'recordId' },
  { title: '科室', dataIndex: 'department', key: 'department' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '操作', key: 'actions', width: 120 }
]

// 表格数据
const data = [
  {
    key: '1',
    name: '张三',
    recordId: 'MR001',
    department: '心内科',
    status: '正常'
  },
  {
    key: '2',
    name: '李四',
    recordId: 'MR002',
    department: '神经外科',
    status: '待审核'
  },
  {
    key: '3',
    name: '王五',
    recordId: 'MR003',
    department: '急诊科',
    status: '正常'
  }
]
</script>

<style scoped>
.layout-test {
  max-width: 1200px;
}
</style>
