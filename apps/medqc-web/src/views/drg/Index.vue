<template>
  <div class="drg-index">
    <!-- 顶部欢迎区 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">DRG/DIP 智能质控平台</h1>
        <p class="welcome-subtitle">基于 AI 的病案首页编码辅助与分组预警系统</p>
        <div class="stats-row">
          <div class="stat-item">
            <div class="stat-value">{{ statistics.pendingCoding }}</div>
            <div class="stat-label">待编码病案</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-value warning">{{ statistics.pendingAlerts }}</div>
            <div class="stat-label">待处理预警</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-value success">{{ statistics.drgGroupRate }}%</div>
            <div class="stat-label">入组率</div>
          </div>
        </div>
      </div>
      <div class="welcome-decoration">
        <img src="https://gw.alipayobjects.com/zos/bmw-prod/677b102c-4740-4c32-b43f-679fc40d3a57.svg" alt="decoration" />
      </div>
    </div>

    <div class="content-wrapper">
      <!-- 核心功能区 (3+2 布局) -->
      <a-row :gutter="[24, 24]">
        <!-- 第一行：核心流程 -->
        <a-col :span="8" v-for="module in mainModules" :key="module.key">
          <div class="feature-card" @click="navigateTo(module.path)">
            <div class="card-bg" :style="{ background: module.gradient }"></div>
            <div class="card-icon" :style="{ color: module.color, background: module.iconBg }">
              <component :is="module.icon" />
            </div>
            <div class="card-info">
              <h3>{{ module.title }}</h3>
              <p>{{ module.description }}</p>
            </div>
            <div class="card-action">
              <ArrowRightOutlined />
            </div>
          </div>
        </a-col>

        <!-- 第二行：分析与监测 -->
        <a-col :span="12" v-for="module in analysisModules" :key="module.key">
           <div class="feature-card horizontal" @click="navigateTo(module.path)">
            <div class="card-icon" :style="{ color: module.color, background: module.iconBg }">
              <component :is="module.icon" />
            </div>
            <div class="card-info">
              <h3>{{ module.title }}</h3>
              <p>{{ module.description }}</p>
            </div>
             <div class="card-action">
              <span class="enter-text">进入功能</span>
              <ArrowRightOutlined />
            </div>
          </div>
        </a-col>
      </a-row>

      <!-- 最近动态与快捷入口 -->
      <a-row :gutter="24" style="margin-top: 24px">
        <a-col :span="16">
          <a-card title="最近操作动态" :bordered="false" class="activity-card">
            <template #extra><a href="#">查看全部</a></template>
            <a-list item-layout="horizontal" :data-source="recentActivities">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta
                    :description="item.time"
                  >
                    <template #title>
                      <span class="activity-title">{{ item.title }}</span>
                      <span class="activity-desc" v-if="item.description"> - {{ item.description }}</span>
                    </template>
                    <template #avatar>
                      <div class="activity-icon" :class="item.type">
                        <component :is="item.icon" />
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card title="智能助手建议" :bordered="false" class="suggestion-card">
             <div class="suggestion-list">
               <div class="suggestion-item" v-for="i in 3" :key="i">
                 <div class="suggestion-icon"><BulbFilled /></div>
                 <div class="suggestion-content">
                   <div class="suggestion-text">发现 3 份病案存在主要诊断选择风险，建议复核。</div>
                   <div class="suggestion-meta">刚刚</div>
                 </div>
               </div>
             </div>
             <a-button type="primary" ghost block style="margin-top: 16px">查看所有建议</a-button>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { useRouter } from 'vue-router'
import {
  EditOutlined,
  ClusterOutlined,
  DashboardOutlined,
  DollarOutlined,
  BarChartOutlined,
  AuditOutlined,
  WarningOutlined,
  BulbOutlined,
  BulbFilled,
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'

const router = useRouter()

/** 模块定义 */
const allModules = [
  {
    key: 'coding',
    title: '编码辅助',
    description: 'ICD 智能编码推荐与规则校验',
    icon: EditOutlined,
    color: '#1890ff',
    iconBg: '#e6f7ff',
    gradient: 'linear-gradient(135deg, #e6f7ff 0%, #ffffff 100%)',
    path: '/dashboard/drg/coding',
    type: 'main'
  },
  {
    key: 'grouping',
    title: 'DRG 分组',
    description: '实时入组预测与费用结构分析',
    icon: ClusterOutlined,
    color: '#52c41a',
    iconBg: '#f6ffed',
    gradient: 'linear-gradient(135deg, #f6ffed 0%, #ffffff 100%)',
    path: '/dashboard/drg/grouping',
    type: 'main'
  },
  {
    key: 'monitor',
    title: '事中监控',
    description: '运行病历实时预警与质控',
    icon: DashboardOutlined,
    color: '#faad14',
    iconBg: '#fffbe6',
    gradient: 'linear-gradient(135deg, #fffbe6 0%, #ffffff 100%)',
    path: '/dashboard/drg/monitor',
    type: 'main'
  },
  {
    key: 'fee-monitoring',
    title: '付费监测',
    description: '医保费用监测与未入组修正建议',
    icon: DollarOutlined,
    color: '#13c2c2',
    iconBg: '#e6fffb',
    gradient: 'linear-gradient(135deg, #e6fffb 0%, #ffffff 100%)',
    path: '/dashboard/drg/fee-monitoring',
    type: 'analysis'
  },
  {
    key: 'analysis',
    title: '事后分析',
    description: 'DRG 综合绩效统计与盈亏分析报表',
    icon: BarChartOutlined,
    color: '#722ed1',
    iconBg: '#f9f0ff',
    gradient: 'linear-gradient(135deg, #f9f0ff 0%, #ffffff 100%)',
    path: '/dashboard/drg/analysis',
    type: 'analysis'
  }
]

const mainModules = computed(() => allModules.filter(m => m.type === 'main'))
const analysisModules = computed(() => allModules.filter(m => m.type === 'analysis'))

/** 统计数据 */
const statistics = ref({
  pendingCoding: 0,
  pendingReview: 0,
  pendingAlerts: 0,
  codingSuggestions: 0,
  drgGroupRate: 98.5
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
    // 模拟数据
    statistics.value = {
      pendingCoding: 12,
      pendingReview: 5,
      pendingAlerts: 3,
      codingSuggestions: 8,
      drgGroupRate: 98.5
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

/** 加载最近操作 */
const loadRecentActivities = async () => {
  try {
    recentActivities.value = [
      {
        title: '完成编码：张三 (ADM20250104001)',
        description: '主要诊断：I21.900 急性心肌梗死',
        icon: CheckCircleOutlined,
        type: 'success',
        time: '2分钟前'
      },
      {
        title: 'DRG 分组预测：李四',
        description: '预测分组：FB19 (心力衰竭，不伴并发症)',
        icon: ClusterOutlined,
        type: 'info',
        time: '10分钟前'
      },
      {
        title: '费用预警确认',
        description: '王五 (ADM...) 药品占比超标',
        icon: WarningOutlined,
        type: 'warning',
        time: '1小时前'
      },
       {
        title: '病案提交审核',
        description: '赵六 (ADM...)',
        icon: ClockCircleOutlined,
        type: 'normal',
        time: '2小时前'
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
  min-height: 100vh;
  background-color: #f0f2f5;

  .welcome-section {
    position: relative;
    padding: 32px 40px;
    background: linear-gradient(120deg, #1890ff 0%, #0050b3 100%);
    color: #fff;
    border-radius: 0 0 24px 24px; // 底部圆角
    margin-bottom: -40px; // 让内容卡片浮上来
    overflow: hidden;
    height: 280px;

    .welcome-content {
      position: relative;
      z-index: 2;
      max-width: 800px;
    }

    .welcome-title {
      font-size: 32px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 8px;
    }

    .welcome-subtitle {
      font-size: 16px;
      opacity: 0.9;
      margin-bottom: 32px;
    }

    .stats-row {
      display: flex;
      align-items: center;
      background: rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(10px);
      padding: 16px 32px;
      border-radius: 12px;
      width: fit-content;
      
      .stat-item {
        text-align: center;
        padding: 0 16px;
        
        .stat-value {
          font-size: 24px;
          font-weight: bold;
          line-height: 1.2;
          
          &.warning { color: #ffec3d; }
          &.success { color: #73d13d; }
        }
        
        .stat-label {
          font-size: 12px;
          opacity: 0.8;
          margin-top: 4px;
        }
      }

      .stat-divider {
        width: 1px;
        height: 30px;
        background: rgba(255,255,255,0.3);
        margin: 0 8px;
      }
    }

    .welcome-decoration {
      position: absolute;
      right: 40px;
      top: 50%;
      transform: translateY(-50%);
      z-index: 1;
      opacity: 0.8;
      
      img {
        height: 200px;
      }
    }
  }

  .content-wrapper {
    padding: 0 24px 24px;
    margin-top: 0;
    max-width: 1400px;
    margin-left: auto;
    margin-right: auto;
  }

  .feature-card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
    height: 100%;
    display: flex;
    flex-direction: column;
    border: 1px solid #f0f0f0;

    &:hover {
      transform: translateY(-5px);
      box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
      border-color: transparent;
      
      .card-action {
        color: #1890ff;
        transform: translateX(5px);
      }
    }

    // 装饰背景
    .card-bg {
      position: absolute;
      top: 0;
      right: 0;
      width: 150px;
      height: 150px;
      border-radius: 0 0 0 100%;
      opacity: 0.5;
      z-index: 0;
      transition: all 0.3s;
    }

    .card-icon {
      width: 56px;
      height: 56px;
      border-radius: 16px;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 24px;
      margin-bottom: 20px;
      z-index: 1;
    }

    .card-info {
      z-index: 1;
      flex: 1;
      
      h3 {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 8px;
        color: #1f1f1f;
      }
      
      p {
        color: #8c8c8c;
        font-size: 14px;
        line-height: 1.5;
        margin-bottom: 0;
      }
    }

    .card-action {
      margin-top: 16px;
      font-size: 20px;
      color: #d9d9d9;
      transition: all 0.3s;
      align-self: flex-end;
      z-index: 1;
      display: flex;
      align-items: center;

      .enter-text {
        font-size: 14px;
        margin-right: 8px;
        opacity: 0;
        transform: translateX(-10px);
        transition: all 0.3s;
      }
    }
    
    &:hover .card-action .enter-text {
      opacity: 1;
      transform: translateX(0);
    }

    // 横向卡片样式
    &.horizontal {
      flex-direction: row;
      align-items: center;
      
      .card-icon {
        margin-bottom: 0;
        margin-right: 20px;
      }
      
      .card-action {
        margin-top: 0;
        align-self: center;
        margin-left: auto;
      }
    }
  }

  .activity-card {
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    
    .activity-icon {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 16px;
      
      &.success { background: #f6ffed; color: #52c41a; }
      &.info { background: #e6f7ff; color: #1890ff; }
      &.warning { background: #fffbe6; color: #faad14; }
      &.normal { background: #f0f2f5; color: #8c8c8c; }
    }
    
    .activity-title {
      font-weight: 500;
      color: #262626;
    }
    .activity-desc {
      color: #8c8c8c;
      font-weight: normal;
    }
  }

  .suggestion-card {
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    height: 100%;

    .suggestion-list {
      .suggestion-item {
        display: flex;
        padding: 12px 0;
        border-bottom: 1px solid #f0f0f0;
        
        &:last-child { border-bottom: none; }
        
        .suggestion-icon {
          color: #faad14;
          font-size: 16px;
          margin-top: 2px;
          margin-right: 12px;
        }
        
        .suggestion-content {
          .suggestion-text {
            color: #595959;
            font-size: 13px;
            margin-bottom: 4px;
            line-height: 1.5;
          }
          .suggestion-meta {
            font-size: 12px;
            color: #bfbfbf;
          }
        }
      }
    }
  }
}

// 响应式调整
@media (max-width: 992px) {
  .drg-index .welcome-section {
    height: auto;
    padding-bottom: 60px;
    
    .welcome-decoration { display: none; }
  }
}
</style>
