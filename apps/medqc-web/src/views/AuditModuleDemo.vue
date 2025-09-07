<!-- 审核模块演示页面 -->
<template>
  <div class="audit-module-demo">
    <!-- 页面头部 -->
    <div class="demo-header">
      <div class="header-content">
        <h1 class="page-title">
          <AuditOutlined />
          人工审核模块演示
        </h1>
        <p class="page-description">
          基于LLM集成质控系统的人工审核功能演示，包括审核任务管理、多级审核、消息通知等核心功能。
        </p>
      </div>
      
      <div class="demo-actions">
        <a-space>
          <a-button @click="initializeDemoData" :loading="initializing">
            <DatabaseOutlined />
            初始化演示数据
          </a-button>
          <a-button @click="resetDemo" type="dashed">
            <ReloadOutlined />
            重置演示
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 功能演示区域 -->
    <div class="demo-content">
      <a-tabs v-model:activeKey="activeTab" size="large" class="demo-tabs">
        <!-- 审核任务管理演示 -->
        <a-tab-pane key="task-management" tab="审核任务管理">
          <template #tab>
            <span>
              <ProjectOutlined />
              审核任务管理
            </span>
          </template>
          
          <div class="demo-section">
            <h3>创建审核任务</h3>
            <a-card class="demo-card">
              <CreateAuditTaskForm
                @task-created="handleTaskCreated"
                @demo-mode="true"
              />
            </a-card>
            
            <h3>任务列表</h3>
            <a-card class="demo-card">
              <AuditTaskList
                :tasks="demoTasks"
                @task-selected="handleTaskSelected"
                demo-mode
              />
            </a-card>
          </div>
        </a-tab-pane>

        <!-- 多级审核演示 -->
        <a-tab-pane key="multi-level-audit" tab="多级审核">
          <template #tab>
            <span>
              <TeamOutlined />
              多级审核
            </span>
          </template>
          
          <div class="demo-section">
            <div class="section-header">
              <h3>多级审核流程演示</h3>
              <a-select
                v-model:value="selectedTaskItem"
                placeholder="选择审核项目"
                style="width: 300px"
                @change="handleTaskItemChange"
              >
                <a-select-option
                  v-for="item in demoTaskItems"
                  :key="item.id"
                  :value="item.id"
                >
                  {{ item.patient_name }} - {{ item.department_name }}
                </a-select-option>
              </a-select>
            </div>
            
            <a-card class="demo-card" v-if="selectedTaskItem">
              <MultiLevelAuditTabs
                :task-item-id="selectedTaskItem"
                :task-item="getCurrentTaskItem()"
                @result-updated="handleAuditResultUpdated"
                @result-submitted="handleAuditResultSubmitted"
              />
            </a-card>
          </div>
        </a-tab-pane>

        <!-- 消息通知演示 -->
        <a-tab-pane key="notifications" tab="消息通知">
          <template #tab>
            <span>
              <BellOutlined />
              消息通知
              <a-badge :count="demoNotificationCount" :offset="[10, -5]" />
            </span>
          </template>
          
          <div class="demo-section">
            <a-row :gutter="24">
              <a-col :span="16">
                <h3>消息通知中心</h3>
                <a-card class="demo-card notification-demo">
                  <NotificationCenter />
                </a-card>
              </a-col>
              
              <a-col :span="8">
                <h3>消息生成测试</h3>
                <a-card class="demo-card">
                  <NotificationTestPanel
                    @notification-sent="handleNotificationSent"
                  />
                </a-card>
              </a-col>
            </a-row>
          </div>
        </a-tab-pane>

        <!-- AI辅助功能演示 -->
        <a-tab-pane key="ai-assistance" tab="AI辅助">
          <template #tab>
            <span>
              <RobotOutlined />
              AI辅助功能
            </span>
          </template>
          
          <div class="demo-section">
            <h3>AI辅助缺陷识别</h3>
            <a-card class="demo-card">
              <AIDefectDetectionDemo
                @defects-detected="handleDefectsDetected"
              />
            </a-card>
            
            <h3>智能消息生成</h3>
            <a-card class="demo-card">
              <SmartMessageGeneratorDemo
                @message-generated="handleMessageGenerated"
              />
            </a-card>
          </div>
        </a-tab-pane>

        <!-- 系统集成演示 -->
        <a-tab-pane key="integration" tab="系统集成">
          <template #tab>
            <span>
              <ApiOutlined />
              系统集成
            </span>
          </template>
          
          <div class="demo-section">
            <h3>与现有LLM质控引擎集成</h3>
            <a-card class="demo-card">
              <LLMIntegrationDemo
                @integration-tested="handleIntegrationTested"
              />
            </a-card>
            
            <h3>Supabase实时功能集成</h3>
            <a-card class="demo-card">
              <SupabaseRealtimeDemo
                @realtime-tested="handleRealtimeTested"
              />
            </a-card>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 演示状态面板 -->
    <div class="demo-status">
      <a-card title="演示状态" size="small">
        <a-descriptions :column="2" size="small">
          <a-descriptions-item label="演示任务数">
            {{ demoTasks.length }}
          </a-descriptions-item>
          <a-descriptions-item label="审核项目数">
            {{ demoTaskItems.length }}
          </a-descriptions-item>
          <a-descriptions-item label="消息通知数">
            {{ demoNotificationCount }}
          </a-descriptions-item>
          <a-descriptions-item label="AI分析次数">
            {{ aiAnalysisCount }}
          </a-descriptions-item>
        </a-descriptions>
        
        <a-divider />
        
        <div class="status-actions">
          <a-space>
            <a-button @click="exportDemoData" size="small">
              <DownloadOutlined />
              导出演示数据
            </a-button>
            <a-button @click="viewDemoLogs" size="small">
              <FileTextOutlined />
              查看日志
            </a-button>
          </a-space>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  AuditOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  ProjectOutlined,
  TeamOutlined,
  BellOutlined,
  RobotOutlined,
  ApiOutlined,
  DownloadOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'

import type { 
  QCAuditTask, 
  QCAuditTaskItem, 
  QCNotification 
} from '@/types/audit-module'

import { auditTaskService } from '@/services/audit-task-service'
import { notificationService } from '@/services/notification-service'
import MultiLevelAuditTabs from '@/components/audit/MultiLevelAuditTabs.vue'
import NotificationCenter from '@/components/notification/NotificationCenter.vue'

// 状态管理
const activeTab = ref('task-management')
const initializing = ref(false)
const selectedTaskItem = ref<string>('')

// 演示数据
const demoTasks = ref<QCAuditTask[]>([])
const demoTaskItems = ref<QCAuditTaskItem[]>([])
const demoNotificationCount = ref(0)
const aiAnalysisCount = ref(0)

// 计算属性
const getCurrentTaskItem = () => {
  return demoTaskItems.value.find(item => item.id === selectedTaskItem.value)
}

// 方法
const initializeDemoData = async () => {
  try {
    initializing.value = true
    message.loading('正在初始化演示数据...', 0)
    
    // 1. 创建演示审核任务
    await createDemoAuditTasks()
    
    // 2. 生成演示任务项目
    await generateDemoTaskItems()
    
    // 3. 创建演示通知
    await createDemoNotifications()
    
    message.destroy()
    message.success('演示数据初始化完成！')
    
  } catch (error) {
    message.destroy()
    message.error(`初始化失败: ${error.message}`)
  } finally {
    initializing.value = false
  }
}

const createDemoAuditTasks = async () => {
  const demoTaskConfigs = [
    {
      task_name: '2024年第四季度常规质控',
      task_type: 'routine' as const,
      audit_level: 'department' as const,
      audit_scope: {
        departments: ['dept_001', 'dept_002'],
        document_types: ['admission_record', 'discharge_summary'],
        date_range: {
          start: '2024-10-01',
          end: '2024-12-31'
        }
      },
      sampling_config: {
        sampling_method: 'stratified' as const,
        sampling_ratio: 0.1,
        stratification_rules: [
          {
            stratum_name: 'A',
            criteria: { risk_level: 'A' },
            sample_ratio: 0.3,
            min_sample_size: 5
          },
          {
            stratum_name: 'B',
            criteria: { risk_level: 'B' },
            sample_ratio: 0.2,
            min_sample_size: 3
          }
        ]
      },
      planned_start_date: '2024-12-01',
      planned_end_date: '2024-12-31',
      assigned_reviewers: ['reviewer_001', 'reviewer_002'],
      description: '第四季度常规质控任务，重点关注病历完整性和规范性'
    },
    {
      task_name: '专项质控-重症医学科',
      task_type: 'special' as const,
      audit_level: 'expert' as const,
      audit_scope: {
        departments: ['icu_001'],
        document_types: ['icu_record', 'critical_care_record'],
        date_range: {
          start: '2024-11-01',
          end: '2024-12-31'
        }
      },
      sampling_config: {
        sampling_method: 'risk_based' as const,
        total_sample_size: 50,
        risk_based_weights: {
          risk_A_weight: 0.6,
          risk_B_weight: 0.3,
          risk_C_weight: 0.1
        }
      },
      planned_start_date: '2024-12-15',
      planned_end_date: '2025-01-15',
      assigned_reviewers: ['expert_001'],
      description: '重症医学科专项质控，关注危重患者病历质量'
    }
  ]

  for (const config of demoTaskConfigs) {
    try {
      const task = await auditTaskService.createAuditTask(config)
      demoTasks.value.push(task)
    } catch (error) {
      console.warn('创建演示任务失败:', error)
    }
  }
}

const generateDemoTaskItems = () => {
  const demoItems: QCAuditTaskItem[] = [
    {
      id: 'item_001',
      task_id: demoTasks.value[0]?.id || 'task_001',
      patient_id: 'patient_001',
      medical_record_id: 'record_001',
      patient_name: '张三',
      admission_date: '2024-11-15',
      discharge_date: '2024-11-20',
      department_id: 'dept_001',
      department_name: '内科',
      risk_level: 'B',
      complexity_score: 75,
      audit_status: 'pending',
      defect_count: 0,
      has_critical_defects: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    },
    {
      id: 'item_002',
      task_id: demoTasks.value[0]?.id || 'task_001',
      patient_id: 'patient_002',
      medical_record_id: 'record_002',
      patient_name: '李四',
      admission_date: '2024-11-18',
      discharge_date: '2024-11-25',
      department_id: 'dept_002',
      department_name: '外科',
      risk_level: 'A',
      complexity_score: 90,
      audit_status: 'in_review',
      defect_count: 2,
      has_critical_defects: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
  ]

  demoTaskItems.value = demoItems
  
  // 默认选择第一个项目
  if (demoItems.length > 0) {
    selectedTaskItem.value = demoItems[0].id
  }
}

const createDemoNotifications = async () => {
  const demoNotifications = [
    {
      type: 'rectification_required' as const,
      recipientType: 'clinician' as const,
      relatedData: {
        patient_id: 'patient_001',
        medical_record_id: 'record_001',
        defect_id: 'defect_001'
      },
      customContent: {
        title: '病历整改通知',
        content: '您的患者张三的病历存在完整性问题，请及时整改。',
        priority: 'high' as const
      }
    },
    {
      type: 'task_assigned' as const,
      recipientType: 'reviewer' as const,
      relatedData: {
        audit_task_id: demoTasks.value[0]?.id || 'task_001'
      },
      customContent: {
        title: '新审核任务分配',
        content: '您有新的审核任务需要处理，请及时查看。',
        priority: 'normal' as const
      }
    }
  ]

  for (const notificationConfig of demoNotifications) {
    try {
      await notificationService.sendNotification(
        'demo_user_001',
        notificationConfig.recipientType,
        notificationConfig.type,
        notificationConfig.relatedData,
        notificationConfig.customContent
      )
      demoNotificationCount.value++
    } catch (error) {
      console.warn('创建演示通知失败:', error)
    }
  }
}

const resetDemo = () => {
  demoTasks.value = []
  demoTaskItems.value = []
  demoNotificationCount.value = 0
  aiAnalysisCount.value = 0
  selectedTaskItem.value = ''
  message.success('演示已重置')
}

const handleTaskCreated = (task: QCAuditTask) => {
  demoTasks.value.push(task)
  message.success('演示任务创建成功')
}

const handleTaskSelected = (task: QCAuditTask) => {
  activeTab.value = 'multi-level-audit'
  message.info(`已选择任务: ${task.task_name}`)
}

const handleTaskItemChange = (itemId: string) => {
  selectedTaskItem.value = itemId
}

const handleAuditResultUpdated = (level: string, result: any) => {
  message.success(`${level}级审核结果已更新`)
}

const handleAuditResultSubmitted = (level: string, result: any) => {
  message.success(`${level}级审核结果已提交`)
}

const handleNotificationSent = (notification: QCNotification) => {
  demoNotificationCount.value++
  message.success('演示通知已发送')
}

const handleDefectsDetected = (defects: any[]) => {
  aiAnalysisCount.value++
  message.success(`AI检测到 ${defects.length} 个潜在缺陷`)
}

const handleMessageGenerated = (message) => {
  aiAnalysisCount.value++
  message.success('智能消息生成成功')
}

const handleIntegrationTested = (result) => {
  message.success('LLM集成测试完成')
}

const handleRealtimeTested = (result) => {
  message.success('实时功能测试完成')
}

const exportDemoData = () => {
  const demoData = {
    tasks: demoTasks.value,
    taskItems: demoTaskItems.value,
    notificationCount: demoNotificationCount.value,
    aiAnalysisCount: aiAnalysisCount.value,
    timestamp: new Date().toISOString()
  }
  
  const blob = new Blob([JSON.stringify(demoData, null, 2)], {
    type: 'application/json'
  })
  
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `audit-module-demo-${Date.now()}.json`
  a.click()
  
  URL.revokeObjectURL(url)
  message.success('演示数据已导出')
}

const viewDemoLogs = () => {
  message.info('演示日志功能开发中...')
}

// 生命周期
onMounted(() => {
  // 自动初始化一些基础演示数据
  generateDemoTaskItems()
})
</script>

<style scoped>
.audit-module-demo {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.demo-header {
  background: white;
  border-radius: 12px;
  padding: 32px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  margin: 0 0 12px 0;
  font-size: 28px;
  font-weight: 700;
  color: #262626;
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-description {
  margin: 0;
  font-size: 16px;
  color: #595959;
  line-height: 1.6;
  max-width: 600px;
}

.demo-content {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  min-height: 600px;
}

.demo-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 32px;
}

.demo-tabs :deep(.ant-tabs-tab) {
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 500;
}

.demo-section {
  padding: 0;
}

.demo-section h3 {
  font-size: 18px;
  font-weight: 600;
  color: #262626;
  margin: 0 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.demo-card {
  margin-bottom: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.demo-card:last-child {
  margin-bottom: 0;
}

.notification-demo {
  height: 500px;
  overflow: hidden;
}

.demo-status {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}

.status-actions {
  margin-top: 16px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .demo-header {
    flex-direction: column;
    gap: 24px;
    align-items: stretch;
  }
  
  .demo-actions {
    align-self: flex-end;
  }
}

@media (max-width: 768px) {
  .audit-module-demo {
    padding: 16px;
  }
  
  .demo-header {
    padding: 24px;
  }
  
  .page-title {
    font-size: 24px;
  }
  
  .demo-content {
    padding: 16px;
  }
  
  .section-header {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }
}

/* 动画效果 */
.demo-card {
  transition: all 0.3s ease;
}

.demo-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.demo-section {
  animation: fadeInUp 0.6s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
