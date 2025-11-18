<template>
  <div class="drg-index">
    <a-page-header
      title="DRG/DIP 系统"
      sub-title="病案首页编码和DRG分组管理"
    />

    <div class="content-wrapper">
      <!-- 功能模块卡片 -->
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :lg="6" v-for="module in modules" :key="module.key">
          <a-card
            class="module-card"
            hoverable
            @click="navigateTo(module.path)"
          >
            <template #cover>
              <div class="card-icon">
                <component :is="module.icon" :style="{ fontSize: '48px', color: module.color }" />
              </div>
            </template>
            <a-card-meta
              :title="module.title"
              :description="module.description"
            />
            <template #actions>
              <span style="color: #1890ff">进入 →</span>
            </template>
          </a-card>
        </a-col>
      </a-row>

      <!-- 快速统计 -->
      <a-row :gutter="16" style="margin-top: 24px">
        <a-col :xs="24" :sm="12" :lg="6">
          <a-card>
            <a-statistic
              title="待编码病案"
              :value="statistics.pendingCoding"
              suffix="份"
            >
              <template #prefix>
                <EditOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12" :lg="6">
          <a-card>
            <a-statistic
              title="待审核病案"
              :value="statistics.pendingReview"
              suffix="份"
            >
              <template #prefix>
                <AuditOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12" :lg="6">
          <a-card>
            <a-statistic
              title="待处理预警"
              :value="statistics.pendingAlerts"
              suffix="条"
            >
              <template #prefix>
                <WarningOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12" :lg="6">
          <a-card>
            <a-statistic
              title="编码建议"
              :value="statistics.codingSuggestions"
              suffix="条"
            >
              <template #prefix>
                <BulbOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- 最近操作记录 -->
      <a-card title="最近操作" style="margin-top: 24px" v-if="recentActivities.length > 0">
        <a-list
          :data-source="recentActivities"
          item-layout="horizontal"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta
                :title="item.title"
                :description="item.description"
              >
                <template #avatar>
                  <a-avatar :style="{ backgroundColor: item.color }">
                    <component :is="item.icon" />
                  </a-avatar>
                </template>
              </a-list-item-meta>
              <template #extra>
                <span style="color: #999">{{ item.time }}</span>
              </template>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  EditOutlined,
  ClusterOutlined,
  DashboardOutlined,
  BarChartOutlined,
  AuditOutlined,
  WarningOutlined,
  BulbOutlined
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'

const router = useRouter()

/** 功能模块 */
const modules = [
  {
    key: 'coding',
    title: '编码辅助',
    description: 'ICD 编码推荐和校验',
    icon: EditOutlined,
    color: '#1890ff',
    path: '/dashboard/drg/coding'
  },
  {
    key: 'grouping',
    title: 'DRG 分组',
    description: 'DRG 入组预测和费用分析',
    icon: ClusterOutlined,
    color: '#52c41a',
    path: '/dashboard/drg/grouping'
  },
  {
    key: 'monitor',
    title: '事中监控',
    description: '实时预警和编码建议',
    icon: DashboardOutlined,
    color: '#faad14',
    path: '/dashboard/drg/monitor'
  },
  {
    key: 'analysis',
    title: '事后分析',
    description: 'DRG 绩效统计和盈亏分析',
    icon: BarChartOutlined,
    color: '#722ed1',
    path: '/dashboard/drg/analysis'
  }
]

/** 统计数据 */
const statistics = ref({
  pendingCoding: 0,
  pendingReview: 0,
  pendingAlerts: 0,
  codingSuggestions: 0
})

/** 最近操作记录 */
const recentActivities = ref<any[]>([])

/** 导航到指定路径 */
const navigateTo = (path: string) => {
  router.push(path)
}

/** 加载统计数据 */
const loadStatistics = async () => {
  try {
    // TODO: 实现统计数据 API
    // 暂时使用模拟数据
    statistics.value = {
      pendingCoding: 12,
      pendingReview: 5,
      pendingAlerts: 3,
      codingSuggestions: 8
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

/** 加载最近操作 */
const loadRecentActivities = async () => {
  try {
    // TODO: 实现最近操作 API
    // 暂时使用模拟数据
    recentActivities.value = [
      {
        title: '完成编码：张三的病案',
        description: '住院号：ADM20250104001',
        icon: h(EditOutlined),
        color: '#1890ff',
        time: '2分钟前'
      },
      {
        title: 'DRG 分组预测',
        description: '心肌梗死 → FB19',
        icon: h(ClusterOutlined),
        color: '#52c41a',
        time: '10分钟前'
      },
      {
        title: '处理预警',
        description: '费用超标预警已确认',
        icon: h(WarningOutlined),
        color: '#faad14',
        time: '1小时前'
      }
    ]
  } catch (error) {
    console.error('加载最近操作失败:', error)
  }
}

onMounted(() => {
  loadStatistics()
  loadRecentActivities()
})
</script>

<style scoped lang="scss">
.drg-index {
  .content-wrapper {
    padding: 24px;
  }

  .module-card {
    .card-icon {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 120px;
      background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transition: all 0.3s;
    }
  }
}
</style>
