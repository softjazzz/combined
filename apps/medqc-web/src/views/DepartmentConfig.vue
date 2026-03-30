<template>
  <div class="department-config">
    <div class="page-header">
      <h1>专科化配置</h1>
      <p>配置不同科室的专科化质控规则和参数</p>
    </div>

    <div class="content-wrapper">
      <!-- 科室选择 -->
      <a-card
        title="科室选择"
        class="department-selector"
      >
        <a-row :gutter="16">
          <a-col :span="8">
            <a-select
              v-model:value="selectedDepartment"
              placeholder="请选择科室"
              style="width: 100%"
              @change="handleDepartmentChange"
            >
              <a-select-option
                v-for="dept in departments"
                :key="dept.id"
                :value="dept.id"
              >
                {{ dept.name }}
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="16">
            <a-space>
              <a-button
                type="primary"
                @click="showAddDepartmentModal = true"
              >
                <template #icon>
                  <PlusOutlined />
                </template>
                添加科室
              </a-button>
              <a-button @click="refreshDepartments">
                <template #icon>
                  <ReloadOutlined />
                </template>
                刷新
              </a-button>
            </a-space>
          </a-col>
        </a-row>
      </a-card>

      <!-- 科室配置详情 -->
      <a-card
        v-if="selectedDepartment"
        :title="`${currentDepartment?.name} - 专科化配置`"
        class="config-details"
      >
        <a-tabs v-model:active-key="activeTab">
          <!-- 基础信息 -->
          <a-tab-pane
            key="basic"
            tab="基础信息"
          >
            <a-form
              :model="departmentConfig"
              layout="vertical"
              @finish="saveDepartmentConfig"
            >
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item
                    label="科室名称"
                    name="name"
                  >
                    <a-input v-model:value="departmentConfig.name" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item
                    label="科室代码"
                    name="code"
                  >
                    <a-input v-model:value="departmentConfig.code" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item
                label="科室描述"
                name="description"
              >
                <a-textarea
                  v-model:value="departmentConfig.description"
                  :rows="3"
                />
              </a-form-item>

              <a-row :gutter="16">
                <a-col :span="8">
                  <a-form-item
                    label="科室类型"
                    name="type"
                  >
                    <a-select v-model:value="departmentConfig.type">
                      <a-select-option value="internal">
                        内科
                      </a-select-option>
                      <a-select-option value="surgical">
                        外科
                      </a-select-option>
                      <a-select-option value="emergency">
                        急诊科
                      </a-select-option>
                      <a-select-option value="icu">
                        重症医学科
                      </a-select-option>
                      <a-select-option value="pediatric">
                        儿科
                      </a-select-option>
                      <a-select-option value="obstetric">
                        妇产科
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
                <a-col :span="8">
                  <a-form-item
                    label="风险等级"
                    name="riskLevel"
                  >
                    <a-select v-model:value="departmentConfig.riskLevel">
                      <a-select-option value="high">
                        高风险
                      </a-select-option>
                      <a-select-option value="medium">
                        中风险
                      </a-select-option>
                      <a-select-option value="low">
                        低风险
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
                <a-col :span="8">
                  <a-form-item
                    label="状态"
                    name="status"
                  >
                    <a-select v-model:value="departmentConfig.status">
                      <a-select-option value="active">
                        启用
                      </a-select-option>
                      <a-select-option value="inactive">
                        禁用
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item>
                <a-button
                  type="primary"
                  html-type="submit"
                  :loading="saving"
                >
                  保存配置
                </a-button>
              </a-form-item>
            </a-form>
          </a-tab-pane>

          <!-- 质控规则 -->
          <a-tab-pane
            key="rules"
            tab="质控规则"
          >
            <div class="rules-section">
              <div class="section-header">
                <h3>专科质控规则</h3>
                <a-button
                  type="primary"
                  @click="showAddRuleModal = true"
                >
                  <template #icon>
                    <PlusOutlined />
                  </template>
                  添加规则
                </a-button>
              </div>

              <a-table
                :columns="rulesColumns"
                :data-source="departmentRules"
                :pagination="false"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'enabled'">
                    <a-switch
                      :checked="record.enabled"
                      @change="(checked: boolean) => toggleRule(record as DepartmentRule, checked)"
                    />
                  </template>
                  <template v-else-if="column.key === 'severity'">
                    <a-tag :color="getSeverityColor(record.severity)">
                      {{ record.severity }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.key === 'actions'">
                    <a-space>
                      <a-button
                        type="link"
                        size="small"
                        @click="editRule(record as DepartmentRule)"
                      >
                        编辑
                      </a-button>
                      <a-popconfirm
                        title="确定要删除这个规则吗？"
                        @confirm="deleteRule(record as DepartmentRule)"
                      >
                        <a-button
                          type="link"
                          size="small"
                          danger
                        >
                          删除
                        </a-button>
                      </a-popconfirm>
                    </a-space>
                  </template>
                </template>
              </a-table>
            </div>
          </a-tab-pane>

          <!-- 参数配置 -->
          <a-tab-pane
            key="parameters"
            tab="参数配置"
          >
            <div class="parameters-section">
              <h3>专科化参数</h3>
              <a-form layout="vertical">
                <a-row :gutter="16">
                  <a-col :span="8">
                    <a-form-item label="抽样比例 (%)">
                      <a-input-number
                        v-model:value="departmentConfig.samplingRate"
                        :min="1"
                        :max="100"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="审核周期 (天)">
                      <a-input-number
                        v-model:value="departmentConfig.auditCycle"
                        :min="1"
                        :max="30"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="质控分数阈值">
                      <a-input-number
                        v-model:value="departmentConfig.scoreThreshold"
                        :min="0"
                        :max="100"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>

                <a-form-item label="特殊配置">
                  <a-checkbox-group v-model:value="departmentConfig.specialConfigs">
                    <a-checkbox value="autoAssign">
                      自动分配审核员
                    </a-checkbox>
                    <a-checkbox value="priorityReview">
                      优先审核
                    </a-checkbox>
                    <a-checkbox value="doubleCheck">
                      双重审核
                    </a-checkbox>
                    <a-checkbox value="expertReview">
                      专家审核
                    </a-checkbox>
                  </a-checkbox-group>
                </a-form-item>

                <a-form-item>
                  <a-button
                    type="primary"
                    :loading="saving"
                    @click="saveParameters"
                  >
                    保存参数
                  </a-button>
                </a-form-item>
              </a-form>
            </div>
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <!-- 空状态 -->
      <a-empty
        v-else
        description="请选择一个科室进行配置"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
      />
    </div>

    <!-- 添加科室模态框 -->
    <a-modal
      v-model:open="showAddDepartmentModal"
      title="添加科室"
      @ok="addDepartment"
      @cancel="cancelAddDepartment"
    >
      <a-form
        :model="newDepartment"
        layout="vertical"
      >
        <a-form-item
          label="科室名称"
          required
        >
          <a-input v-model:value="newDepartment.name" />
        </a-form-item>
        <a-form-item
          label="科室代码"
          required
        >
          <a-input v-model:value="newDepartment.code" />
        </a-form-item>
        <a-form-item label="科室类型">
          <a-select v-model:value="newDepartment.type">
            <a-select-option value="internal">
              内科
            </a-select-option>
            <a-select-option value="surgical">
              外科
            </a-select-option>
            <a-select-option value="emergency">
              急诊科
            </a-select-option>
            <a-select-option value="icu">
              重症医学科
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message, Empty } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'

interface DepartmentRule {
  id: string
  name: string
  description: string
  severity: 'high' | 'medium' | 'low'
  enabled: boolean
}

// 响应式数据
const selectedDepartment = ref('')
const activeTab = ref('basic')
const saving = ref(false)
const showAddDepartmentModal = ref(false)
const showAddRuleModal = ref(false)

// 科室列表
const departments = ref([
  { id: '1', name: '心内科', code: 'CARDIO', type: 'internal' },
  { id: '2', name: '神经外科', code: 'NEURO', type: 'surgical' },
  { id: '3', name: '急诊科', code: 'EMERG', type: 'emergency' },
  { id: '4', name: 'ICU', code: 'ICU', type: 'icu' },
])

// 当前科室
const currentDepartment = computed(() =>
  departments.value.find((d) => d.id === selectedDepartment.value),
)

// 科室配置
const departmentConfig = reactive({
  name: '',
  code: '',
  description: '',
  type: '',
  riskLevel: 'medium',
  status: 'active',
  samplingRate: 10,
  auditCycle: 7,
  scoreThreshold: 80,
  specialConfigs: [],
})

// 新科室表单
const newDepartment = reactive({
  name: '',
  code: '',
  type: 'internal',
})

// 科室规则
const departmentRules = ref<DepartmentRule[]>([
  {
    id: '1',
    name: '心内科病历完整性检查',
    description: '检查心内科病历必填项',
    severity: 'high',
    enabled: true,
  },
  {
    id: '2',
    name: '用药合理性验证',
    description: '验证心血管用药的合理性',
    severity: 'medium',
    enabled: true,
  },
])

// 规则表格列
const rulesColumns = [
  { title: '规则名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '严重程度', dataIndex: 'severity', key: 'severity' },
  { title: '启用状态', dataIndex: 'enabled', key: 'enabled' },
  { title: '操作', key: 'actions', width: 150 },
]

// 方法
const handleDepartmentChange = (value: string) => {
  const dept = departments.value.find((d) => d.id === value)
  if (dept) {
    Object.assign(departmentConfig, {
      name: dept.name,
      code: dept.code,
      type: dept.type,
      description: `${dept.name}的专科化配置`,
      riskLevel: 'medium',
      status: 'active',
      samplingRate: 10,
      auditCycle: 7,
      scoreThreshold: 80,
      specialConfigs: [],
    })
  }
}

const refreshDepartments = async () => {
  try {
    // 模拟API调用
    await new Promise((resolve) => setTimeout(resolve, 1000))
    message.success('科室列表已刷新')
  } catch (error) {
    message.error('刷新失败')
  }
}

const saveDepartmentConfig = async () => {
  saving.value = true
  try {
    // 模拟API调用
    await new Promise((resolve) => setTimeout(resolve, 1000))
    message.success('科室配置已保存')
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const saveParameters = async () => {
  saving.value = true
  try {
    // 模拟API调用
    await new Promise((resolve) => setTimeout(resolve, 1000))
    message.success('参数配置已保存')
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const addDepartment = async () => {
  try {
    const newDept = {
      id: Date.now().toString(),
      ...newDepartment,
    }
    departments.value.push(newDept)
    message.success('科室添加成功')
    showAddDepartmentModal.value = false
    Object.assign(newDepartment, { name: '', code: '', type: 'internal' })
  } catch (error) {
    message.error('添加失败')
  }
}

const cancelAddDepartment = () => {
  showAddDepartmentModal.value = false
  Object.assign(newDepartment, { name: '', code: '', type: 'internal' })
}

const toggleRule = (rule: DepartmentRule, checked: boolean) => {
  rule.enabled = checked
  message.success(`规则已${checked ? '启用' : '禁用'}`)
}

const editRule = (rule: DepartmentRule) => {
  message.info(`编辑规则: ${rule.name}`)
}

const deleteRule = (rule: DepartmentRule) => {
  const index = departmentRules.value.findIndex((r) => r.id === rule.id)
  if (index > -1) {
    departmentRules.value.splice(index, 1)
    message.success('规则已删除')
  }
}

const getSeverityColor = (severity: string) => {
  const colors: Record<'high' | 'medium' | 'low', string> = {
    high: 'red',
    medium: 'orange',
    low: 'green',
  }
  return severity in colors ? colors[severity as keyof typeof colors] : 'default'
}

// 生命周期
onMounted(() => {
  refreshDepartments()
})
</script>

<style scoped>
.department-config {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  margin: 0;
  color: #666;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.department-selector {
  margin-bottom: 24px;
}

.config-details {
  flex: 1;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
}

.rules-section,
.parameters-section {
  padding: 16px 0;
}
</style>
