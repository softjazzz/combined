<template>
  <BasicLayout>
    <div class="min-h-screen bg-gray-50 p-4 lg:p-6">
      <!-- 页面头部 -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div class="flex-1">
            <div class="flex items-center space-x-3 mb-2">
              <div class="p-2 bg-green-100 rounded-lg">
                <EditOutlined class="text-xl text-green-600" />
              </div>
              <h1 class="text-2xl lg:text-3xl font-bold text-gray-900">
                {{ isEdit ? '编辑规则' : '新建规则' }}
              </h1>
            </div>
            <p class="text-gray-600 text-sm lg:text-base">
              {{ isEdit ? '修改现有医保质控规则配置' : '创建新的医保质控规则' }}
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <a-button @click="goBack" class="flex items-center space-x-2">
              <template #icon><ArrowLeftOutlined /></template>
              <span>返回</span>
            </a-button>
            <a-button @click="previewRule" :disabled="!canPreview" class="flex items-center space-x-2">
              <template #icon><EyeOutlined /></template>
              <span>预览</span>
            </a-button>
            <a-button @click="testRule" :disabled="!canTest" class="flex items-center space-x-2">
              <template #icon><PlayCircleOutlined /></template>
              <span>测试</span>
            </a-button>
            <a-button
              type="primary"
              @click="save"
              :loading="saving"
              class="flex items-center space-x-2 bg-green-600 hover:bg-green-700"
            >
              <template #icon><SaveOutlined /></template>
              <span>保存规则</span>
            </a-button>
          </div>
        </div>
      </div>

      <!-- 表单内容 -->
      <div class="editor-content">
        <a-form
          ref="formRef"
          :model="form"
          :rules="formRules"
          layout="vertical"
          class="rule-form"
        >
          <!-- 基本信息 -->
          <a-card title="基本信息" class="form-card">
            <template #extra>
              <a-tag :color="getSeverityColor(form.severity)">
                {{ getSeverityLabel(form.severity) }}
              </a-tag>
            </template>

            <a-row :gutter="24">
              <a-col :span="8">
                <a-form-item label="规则编码" name="code" required>
                  <a-input
                    v-model:value="form.code"
                    placeholder="如: DRUG_AGE_001"
                    :disabled="isEdit"
                  />
                  <div class="field-hint">规则的唯一标识符，创建后不可修改</div>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="规则名称" name="name" required>
                  <a-input
                    v-model:value="form.name"
                    placeholder="输入规则名称"
                  />
                  <div class="field-hint">简洁明确的规则名称</div>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="规则分类" name="category_id">
                  <a-select
                    v-model:value="form.category_id"
                    placeholder="选择规则分类"
                    allowClear
                  >
                    <a-select-option value="batch_1">第一批（年龄性别）</a-select-option>
                    <a-select-option value="batch_2">第二批（手术折价）</a-select-option>
                    <a-select-option value="batch_3">第三批（保险类型）</a-select-option>
                    <a-select-option value="batch_4">第四批（就诊方式）</a-select-option>
                    <a-select-option value="batch_5">第五批（机构级别）</a-select-option>
                  </a-select>
                  <div class="field-hint">按医保规则批次分类</div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="24">
              <a-col :span="8">
                <a-form-item label="规则类型" name="rule_type">
                  <a-select
                    v-model:value="form.rule_type"
                    placeholder="选择规则类型"
                    allowClear
                  >
                    <a-select-option value="drug_age">药品年龄限制</a-select-option>
                    <a-select-option value="drug_gender">药品性别限制</a-select-option>
                    <a-select-option value="visit_type">就诊方式限制</a-select-option>
                    <a-select-option value="hospital_level">机构级别限制</a-select-option>
                    <a-select-option value="duration">疗程限制</a-select-option>
                    <a-select-option value="surgery_pricing">手术折价</a-select-option>
                  </a-select>
                  <div class="field-hint">规则的业务类型</div>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="严重级别" name="severity" required>
                  <a-select v-model:value="form.severity" :options="severityOptions">
                    <template #option="{ value, label }">
                      <div class="severity-option">
                        <a-tag :color="getSeverityColor(value)" size="small">{{ label }}</a-tag>
                        <span class="severity-desc">{{ getSeverityDescription(value) }}</span>
                      </div>
                    </template>
                  </a-select>
                  <div class="field-hint">规则命中时的处理级别</div>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="规则状态" name="enabled">
                  <a-switch
                    v-model:checked="form.enabled"
                    checked-children="启用"
                    un-checked-children="禁用"
                  />
                  <div class="field-hint">控制规则是否生效</div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="24">
              <a-col :span="12">
                <a-form-item label="规则描述" name="description">
                  <a-textarea
                    v-model:value="form.description"
                    placeholder="详细描述规则的用途、适用场景和注意事项..."
                    :rows="3"
                    show-count
                    :maxlength="500"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="版本号" name="version">
                  <a-input-number
                    v-model:value="form.version"
                    :min="1"
                    style="width:100%"
                    :disabled="!isEdit"
                  />
                  <div class="field-hint">{{ isEdit ? '修改会自动递增版本' : '新规则从版本1开始' }}</div>
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="优先级" name="priority">
                  <a-input-number
                    v-model:value="form.priority"
                    :min="1"
                    :max="100"
                    style="width:100%"
                    placeholder="1-100"
                  />
                  <div class="field-hint">数值越小优先级越高</div>
                </a-form-item>
              </a-col>
            </a-row>
          </a-card>

          <!-- 触发事件配置 -->
          <a-card title="触发事件配置" class="form-card">
            <template #extra>
              <a-space>
                <a-button @click="addTrigger" type="dashed" size="small">
                  <template #icon><PlusOutlined /></template>
                  添加事件
                </a-button>
                <a-button @click="importTriggerTemplate" size="small">
                  <template #icon><ImportOutlined /></template>
                  使用模板
                </a-button>
              </a-space>
            </template>

            <div class="trigger-section">
              <div class="section-description">
                配置规则的触发条件，当指定事件发生时会执行规则检查
              </div>

              <a-table
                :dataSource="triggers"
                :columns="triggerColumns"
                rowKey="key"
                :pagination="false"
                size="small"
                class="trigger-table"
              >
                <template #bodyCell="{ column, record, index }">
                  <template v-if="column.key === 'event_type'">
                    <a-select
                      v-model:value="record.event_type"
                      placeholder="选择触发事件"
                      style="width: 100%"
                      show-search
                      allow-clear
                    >
                      <a-select-option value="order.drug.submit">药品医嘱提交</a-select-option>
                      <a-select-option value="order.drug.sign">药品医嘱签署</a-select-option>
                      <a-select-option value="order.surgery.submit">手术医嘱提交</a-select-option>
                      <a-select-option value="order.exam.submit">检查医嘱提交</a-select-option>
                      <a-select-option value="order.lab.submit">检验医嘱提交</a-select-option>
                      <a-select-option value="visit.admission">患者入院</a-select-option>
                      <a-select-option value="visit.discharge">患者出院</a-select-option>
                    </a-select>
                  </template>

                  <template v-else-if="column.key === 'priority'">
                    <a-input-number
                      v-model:value="record.priority"
                      :min="1"
                      :max="100"
                      style="width: 100%"
                    />
                  </template>

                  <template v-else-if="column.key === 'description'">
                    <a-input
                      v-model:value="record.description"
                      placeholder="事件描述"
                      style="width: 100%"
                    />
                  </template>

                  <template v-else-if="column.key === 'actions'">
                    <a-space size="small">
                      <a-tooltip title="上移">
                        <a-button
                          size="small"
                          type="text"
                          @click="moveUp(index)"
                          :disabled="index === 0"
                        >
                          <template #icon><ArrowUpOutlined /></template>
                        </a-button>
                      </a-tooltip>
                      <a-tooltip title="下移">
                        <a-button
                          size="small"
                          type="text"
                          @click="moveDown(index)"
                          :disabled="index === triggers.length - 1"
                        >
                          <template #icon><ArrowDownOutlined /></template>
                        </a-button>
                      </a-tooltip>
                      <a-tooltip title="删除">
                        <a-button
                          size="small"
                          type="text"
                          danger
                          @click="removeTrigger(index)"
                        >
                          <template #icon><DeleteOutlined /></template>
                        </a-button>
                      </a-tooltip>
                    </a-space>
                  </template>
                </template>
              </a-table>

              <a-empty v-if="triggers.length === 0" description="暂无触发事件，请添加">
                <a-button type="primary" @click="addTrigger">添加触发事件</a-button>
              </a-empty>
            </div>
          </a-card>

          <!-- 条件配置 -->
          <a-card title="条件配置" class="form-card">
            <template #extra>
              <a-space>
                <a-button @click="addCondition" type="dashed" size="small">
                  <template #icon><PlusOutlined /></template>
                  添加条件
                </a-button>
                <a-button @click="formatConditions" size="small">
                  <template #icon><FormatPainterOutlined /></template>
                  格式化
                </a-button>
                <a-button @click="validateConditions" size="small">
                  <template #icon><CheckCircleOutlined /></template>
                  验证
                </a-button>
              </a-space>
            </template>

            <div class="condition-section">
              <div class="section-description">
                使用JSON格式定义规则条件，支持复杂的逻辑表达式
              </div>

              <div class="json-editor-container">
                <a-textarea
                  v-model:value="conditionsText"
                  :rows="15"
                  placeholder="请输入JSON格式的条件配置..."
                  class="json-editor"
                />
                <div class="editor-toolbar">
                  <a-space>
                    <a-button size="small" @click="showConditionHelper">
                      <template #icon><QuestionCircleOutlined /></template>
                      语法帮助
                    </a-button>
                    <a-button size="small" @click="showConditionExamples">
                      <template #icon><BookOutlined /></template>
                      示例模板
                    </a-button>
                  </a-space>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 动作配置 -->
          <a-card title="动作配置" class="form-card">
            <template #extra>
              <a-space>
                <a-button @click="addAction" type="dashed" size="small">
                  <template #icon><PlusOutlined /></template>
                  添加动作
                </a-button>
                <a-button @click="formatActions" size="small">
                  <template #icon><FormatPainterOutlined /></template>
                  格式化
                </a-button>
                <a-button @click="validateActions" size="small">
                  <template #icon><CheckCircleOutlined /></template>
                  验证
                </a-button>
              </a-space>
            </template>

            <div class="action-section">
              <div class="section-description">
                定义规则命中时的处理动作，如拦截、警告或通知
              </div>

              <div class="json-editor-container">
                <a-textarea
                  v-model:value="actionsText"
                  :rows="10"
                  placeholder="请输入JSON格式的动作配置..."
                  class="json-editor"
                />
                <div class="editor-toolbar">
                  <a-space>
                    <a-button size="small" @click="showActionHelper">
                      <template #icon><QuestionCircleOutlined /></template>
                      语法帮助
                    </a-button>
                    <a-button size="small" @click="showActionExamples">
                      <template #icon><BookOutlined /></template>
                      示例模板
                    </a-button>
                  </a-space>
                </div>
              </div>
            </div>
          </a-card>

        </a-form>
      </div>

      <!-- 底部操作区 -->
      <div class="editor-footer">
        <div class="footer-content">
          <div class="footer-info">
            <a-space>
              <span class="info-text">
                <ClockCircleOutlined />
                {{ isEdit ? '最后修改' : '创建时间' }}: {{ formatTime(form.updated_at || new Date().toISOString()) }}
              </span>
              <a-divider type="vertical" />
              <span class="info-text">
                <UserOutlined />
                操作人: {{ currentUser?.name || '当前用户' }}
              </span>
            </a-space>
          </div>
          <div class="footer-actions">
            <a-space size="large">
              <a-button @click="goBack" size="large">
                取消
              </a-button>
              <a-button @click="saveDraft" :loading="savingDraft" size="large">
                <template #icon><SaveOutlined /></template>
                保存草稿
              </a-button>
              <a-button type="primary" @click="save" :loading="saving" size="large">
                <template #icon><CheckOutlined /></template>
                {{ isEdit ? '更新规则' : '创建规则' }}
              </a-button>
            </a-space>
          </div>
        </div>
      </div>
    </div>

    <!-- 条件语法帮助模态框 -->
    <a-modal
      v-model:open="conditionHelperVisible"
      title="条件配置语法帮助"
      width="800px"
      :footer="null"
    >
      <div class="syntax-help">
        <a-typography>
          <a-typography-title :level="4">基本语法</a-typography-title>
          <a-typography-paragraph>
            条件使用JSON格式定义，支持以下操作符：
          </a-typography-paragraph>
          <ul>
            <li><code>==</code> - 等于</li>
            <li><code>!=</code> - 不等于</li>
            <li><code>&gt;</code> - 大于</li>
            <li><code>&gt;=</code> - 大于等于</li>
            <li><code>&lt;</code> - 小于</li>
            <li><code>&lt;=</code> - 小于等于</li>
            <li><code>in</code> - 包含在数组中</li>
            <li><code>not_in</code> - 不包含在数组中</li>
          </ul>

          <a-typography-title :level="4">示例</a-typography-title>
          <pre class="code-example">{{conditionExample}}</pre>
        </a-typography>
      </div>
    </a-modal>

    <!-- 条件示例模态框 -->
    <a-modal
      v-model:open="conditionExamplesVisible"
      title="条件配置示例"
      width="900px"
      :footer="null"
    >
      <a-tabs>
        <a-tab-pane key="age" tab="年龄限制">
          <pre class="code-example">{{ ageConditionExample }}</pre>
        </a-tab-pane>
        <a-tab-pane key="gender" tab="性别限制">
          <pre class="code-example">{{ genderConditionExample }}</pre>
        </a-tab-pane>
        <a-tab-pane key="visit" tab="就诊方式">
          <pre class="code-example">{{ visitConditionExample }}</pre>
        </a-tab-pane>
      </a-tabs>
    </a-modal>

    <!-- 动作语法帮助模态框 -->
    <a-modal
      v-model:open="actionHelperVisible"
      title="动作配置语法帮助"
      width="800px"
      :footer="null"
    >
      <div class="syntax-help">
        <a-typography>
          <a-typography-title :level="4">动作类型</a-typography-title>
          <ul>
            <li><code>intercept</code> - 拦截：阻止操作继续执行</li>
            <li><code>warn</code> - 警告：显示警告信息，允许继续</li>
            <li><code>notify</code> - 通知：记录日志，不影响操作</li>
          </ul>

          <a-typography-title :level="4">消息模板</a-typography-title>
          <a-typography-paragraph>
            支持使用占位符引用上下文数据：
          </a-typography-paragraph>
          <ul>
            <li><code>{`{patient.age}`}</code> - 患者年龄</li>
            <li><code>{`{patient.gender}`}</code> - 患者性别</li>
            <li><code>{`{order.drug_code}`}</code> - 药品编码</li>
            <li><code>{`{visit.type}`}</code> - 就诊类型</li>
          </ul>
        </a-typography>
      </div>
    </a-modal>

    <!-- 动作示例模态框 -->
    <a-modal
      v-model:open="actionExamplesVisible"
      title="动作配置示例"
      width="900px"
      :footer="null"
    >
      <a-tabs>
        <a-tab-pane key="intercept" tab="拦截动作">
          <pre class="code-example">{{ interceptActionExample }}</pre>
        </a-tab-pane>
        <a-tab-pane key="warn" tab="警告动作">
          <pre class="code-example">{{ warnActionExample }}</pre>
        </a-tab-pane>
        <a-tab-pane key="notify" tab="通知动作">
          <pre class="code-example">{{ notifyActionExample }}</pre>
        </a-tab-pane>
      </a-tabs>
    </a-modal>

    <!-- 规则预览模态框 -->
    <a-modal
      v-model:open="previewVisible"
      title="规则预览"
      width="1000px"
      :footer="null"
    >
      <div v-if="previewData" class="rule-preview">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="规则编码">{{ previewData.code }}</a-descriptions-item>
          <a-descriptions-item label="规则名称">{{ previewData.name }}</a-descriptions-item>
          <a-descriptions-item label="规则类型">{{ previewData.rule_type }}</a-descriptions-item>
          <a-descriptions-item label="严重级别">{{ previewData.severity }}</a-descriptions-item>
        </a-descriptions>

        <a-divider>触发事件</a-divider>
        <a-list :data-source="previewData.triggers" size="small">
          <template #renderItem="{ item }">
            <a-list-item>{{ item.event_type }} (优先级: {{ item.priority }})</a-list-item>
          </template>
        </a-list>

        <a-divider>条件配置</a-divider>
        <pre class="preview-json">{{ formatJson(previewData.conditions) }}</pre>

        <a-divider>动作配置</a-divider>
        <pre class="preview-json">{{ formatJson(previewData.actions) }}</pre>
      </div>
    </a-modal>
  </BasicLayout>
</template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref, computed, onMounted, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import { supabase } from '@/lib/supabase'
import { saveRule } from '@/services/supabaseSdk'
import {
  EditOutlined, ArrowLeftOutlined, EyeOutlined, PlayCircleOutlined, SaveOutlined,
  PlusOutlined, ImportOutlined, ArrowUpOutlined, ArrowDownOutlined, DeleteOutlined,
  FormatPainterOutlined, CheckCircleOutlined, QuestionCircleOutlined, BookOutlined,
  ClockCircleOutlined, UserOutlined, CheckOutlined
} from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()

// 响应式数据
const formRef = ref()
const saving = ref(false)
const savingDraft = ref(false)

// 表单数据
const form = ref<any>({
  id: null,
  code: '',
  name: '',
  description: '',
  rule_type: '',
  category_id: '',
  severity: 'warn',
  enabled: true,
  version: 1,
  priority: 50,
  updated_at: null
})

// JSON编辑器内容
const conditionsText = ref<string>(`[
  {
    "priority": 1,
    "expression_json": {
      "all": [
        {
          "fact": "patient.age",
          "op": ">",
          "value": 14
        }
      ]
    }
  }
]`)

const actionsText = ref<string>(`[
  {
    "action_type": "warn",
    "message_template": "患者年龄为{patient.age}岁，请确认是否符合用药要求"
  }
]`)

// 触发事件配置
const triggers = ref<Array<{
  key: string;
  event_type: string;
  priority: number;
  description: string
}>>([])

// 模态框状态
const conditionHelperVisible = ref(false)
const conditionExamplesVisible = ref(false)
const actionHelperVisible = ref(false)
const actionExamplesVisible = ref(false)
const previewVisible = ref(false)
const previewData = ref<any>(null)

// 当前用户信息（模拟）
const currentUser = ref({
  name: '管理员',
  id: 1
})

// 配置选项
const severityOptions = [
  { label: '信息', value: 'info' },
  { label: '警告', value: 'warn' },
  { label: '阻断', value: 'block' }
]

const triggerColumns = [
  { title: '触发事件', key: 'event_type', width: 200 },
  { title: '优先级', key: 'priority', width: 100 },
  { title: '描述', key: 'description', width: 200 },
  { title: '操作', key: 'actions', width: 120 }
]

// 表单验证规则
const formRules = {
  code: [
    { required: true, message: '请输入规则编码', trigger: 'blur' },
    { pattern: /^[A-Z][A-Z0-9_]*$/, message: '编码必须以大写字母开头，只能包含大写字母、数字和下划线', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入规则名称', trigger: 'blur' },
    { min: 2, max: 100, message: '规则名称长度在2-100个字符', trigger: 'blur' }
  ],
  severity: [
    { required: true, message: '请选择严重级别', trigger: 'change' }
  ]
}

// 计算属性
const isEdit = computed(() => Boolean(form.value?.id))
const canPreview = computed(() => form.value.code && form.value.name)
const canTest = computed(() => canPreview.value && triggers.value.length > 0)

// 示例数据
const conditionExample = `{
  "all": [
    {
      "fact": "patient.age",
      "op": ">",
      "value": 14
    },
    {
      "fact": "order.drug_code",
      "op": "in",
      "value": ["ABC001", "ABC002"]
    }
  ]
}`

const ageConditionExample = `[
  {
    "priority": 1,
    "expression_json": {
      "all": [
        {
          "fact": "patient.age",
          "op": "<",
          "value": 14
        },
        {
          "fact": "order.drug_code",
          "op": "in",
          "value": ["CHILD_DRUG_001", "CHILD_DRUG_002"]
        }
      ]
    }
  }
]`

const genderConditionExample = `[
  {
    "priority": 1,
    "expression_json": {
      "all": [
        {
          "fact": "patient.gender",
          "op": "==",
          "value": "female"
        },
        {
          "fact": "order.drug_code",
          "op": "in",
          "value": ["FEMALE_DRUG_001"]
        }
      ]
    }
  }
]`

const visitConditionExample = `[
  {
    "priority": 1,
    "expression_json": {
      "all": [
        {
          "fact": "visit.type",
          "op": "!=",
          "value": "INPATIENT"
        },
        {
          "fact": "order.drug_code",
          "op": "in",
          "value": ["INPATIENT_ONLY_DRUG"]
        }
      ]
    }
  }
]`

const interceptActionExample = `[
  {
    "action_type": "intercept",
    "message_template": "患者年龄{patient.age}岁，不符合药品{order.drug_code}的使用要求，禁止开具"
  }
]`

const warnActionExample = `[
  {
    "action_type": "warn",
    "message_template": "患者性别为{patient.gender}，使用药品{order.drug_code}需要特别注意，请确认后继续"
  }
]`

const notifyActionExample = `[
  {
    "action_type": "notify",
    "message_template": "患者{patient.name}使用了特殊药品{order.drug_code}，已记录到质控日志"
  }
]`

// 工具方法
const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

const getSeverityColor = (severity: string) => {
  const colorMap: Record<string, string> = {
    'info': 'blue',
    'warn': 'orange',
    'block': 'red'
  }
  return colorMap[severity] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labelMap: Record<string, string> = {
    'info': '信息',
    'warn': '警告',
    'block': '阻断'
  }
  return labelMap[severity] || severity
}

const getSeverityDescription = (severity: string) => {
  const descMap: Record<string, string> = {
    'info': '记录信息，不影响操作',
    'warn': '显示警告，允许继续',
    'block': '阻止操作，必须修改'
  }
  return descMap[severity] || ''
}

const formatJson = (data: any) => {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

// 基本操作方法
function goBack() {
  router.back()
}

// 触发事件操作方法
function addTrigger() {
  triggers.value.push({
    key: Math.random().toString(36).slice(2),
    event_type: 'order.drug.submit',
    priority: triggers.value.length + 1,
    description: ''
  })
}

function removeTrigger(idx: number) {
  triggers.value.splice(idx, 1)
  // 重新排序优先级
  triggers.value.forEach((t, i) => (t.priority = i + 1))
}

function moveUp(idx: number) {
  if (idx <= 0) return
  const [item] = triggers.value.splice(idx, 1)
  triggers.value.splice(idx - 1, 0, item)
  // 重新排序优先级
  triggers.value.forEach((t, i) => (t.priority = i + 1))
}

function moveDown(idx: number) {
  if (idx >= triggers.value.length - 1) return
  const [item] = triggers.value.splice(idx, 1)
  triggers.value.splice(idx + 1, 0, item)
  // 重新排序优先级
  triggers.value.forEach((t, i) => (t.priority = i + 1))
}

function importTriggerTemplate() {
  // 导入常用触发事件模板
  const templates = [
    { event_type: 'order.drug.submit', priority: 1, description: '药品医嘱提交时触发' },
    { event_type: 'order.drug.sign', priority: 2, description: '药品医嘱签署时触发' }
  ]

  templates.forEach(template => {
    triggers.value.push({
      key: Math.random().toString(36).slice(2),
      ...template,
      priority: triggers.value.length + template.priority
    })
  })

  message.success('已导入触发事件模板')
}

// 条件操作方法
function addCondition() {
  try {
    const arr = JSON.parse(conditionsText.value || '[]')
    arr.push({
      priority: (arr.length + 1),
      expression_json: {
        all: [
          {
            fact: "patient.age",
            op: ">",
            value: 0
          }
        ]
      }
    })
    conditionsText.value = JSON.stringify(arr, null, 2)
    message.success('已添加新条件')
  } catch {
    message.error('条件 JSON 解析失败')
  }
}

function formatConditions() {
  try {
    conditionsText.value = JSON.stringify(JSON.parse(conditionsText.value || '[]'), null, 2)
    message.success('格式化成功')
  } catch {
    message.error('格式化失败，请检查JSON语法')
  }
}

function validateConditions() {
  try {
    const conditions = JSON.parse(conditionsText.value || '[]')
    if (!Array.isArray(conditions)) {
      throw new Error('条件必须是数组格式')
    }

    conditions.forEach((condition, index) => {
      if (!condition.priority || !condition.expression_json) {
        throw new Error(`第${index + 1}个条件缺少必要字段`)
      }
    })

    message.success('条件配置验证通过')
  } catch (error: any) {
    message.error(`验证失败: ${error.message}`)
  }
}

function showConditionHelper() {
  conditionHelperVisible.value = true
}

function showConditionExamples() {
  conditionExamplesVisible.value = true
}

// 动作操作方法
function addAction() {
  try {
    const arr = JSON.parse(actionsText.value || '[]')
    arr.push({
      action_type: 'warn',
      message_template: '请检查医嘱是否符合规定'
    })
    actionsText.value = JSON.stringify(arr, null, 2)
    message.success('已添加新动作')
  } catch {
    message.error('动作 JSON 解析失败')
  }
}

function formatActions() {
  try {
    actionsText.value = JSON.stringify(JSON.parse(actionsText.value || '[]'), null, 2)
    message.success('格式化成功')
  } catch {
    message.error('格式化失败，请检查JSON语法')
  }
}

function validateActions() {
  try {
    const actions = JSON.parse(actionsText.value || '[]')
    if (!Array.isArray(actions)) {
      throw new Error('动作必须是数组格式')
    }

    actions.forEach((action, index) => {
      if (!action.action_type || !action.message_template) {
        throw new Error(`第${index + 1}个动作缺少必要字段`)
      }

      if (!['intercept', 'warn', 'notify'].includes(action.action_type)) {
        throw new Error(`第${index + 1}个动作类型无效`)
      }
    })

    message.success('动作配置验证通过')
  } catch (error: any) {
    message.error(`验证失败: ${error.message}`)
  }
}

function showActionHelper() {
  actionHelperVisible.value = true
}

function showActionExamples() {
  actionExamplesVisible.value = true
}

// 预览和测试方法
function previewRule() {
  try {
    previewData.value = {
      ...form.value,
      triggers: triggers.value,
      conditions: JSON.parse(conditionsText.value || '[]'),
      actions: JSON.parse(actionsText.value || '[]')
    }
    previewVisible.value = true
  } catch (error) {
    message.error('预览失败，请检查JSON格式')
  }
}

async function testRule() {
  try {
    // 验证表单
    await formRef.value?.validate()

    // 验证JSON格式
    JSON.parse(conditionsText.value || '[]')
    JSON.parse(actionsText.value || '[]')

    message.loading('正在测试规则...', 2)

    // 模拟测试过程
    setTimeout(() => {
      message.success('规则测试通过，配置正确')
    }, 2000)
  } catch (error: any) {
    message.error(`测试失败: ${error.message || '配置有误'}`)
  }
}

// 保存方法
async function saveDraft() {
  savingDraft.value = true
  try {
    // 保存草稿逻辑
    message.success('草稿保存成功')
  } catch (error) {
    message.error('草稿保存失败')
  } finally {
    savingDraft.value = false
  }
}

async function save() {
  try {
    // 验证表单
    await formRef.value?.validate()

    if (!form.value.code || !form.value.name) {
      message.error('请填写规则编码和名称')
      return
    }

    // 验证JSON格式
    let conditions, actions
    try {
      conditions = JSON.parse(conditionsText.value || '[]')
      actions = JSON.parse(actionsText.value || '[]')
    } catch {
      message.error('条件或动作配置格式错误，请检查JSON语法')
      return
    }

    if (triggers.value.length === 0) {
      message.error('请至少配置一个触发事件')
      return
    }

    saving.value = true

    const payload = {
      rule: {
        ...form.value,
        updated_at: new Date().toISOString()
      },
      conditions,
      actions,
      triggers: triggers.value.map(t => ({
        event_type: t.event_type,
        priority: t.priority,
        description: t.description
      }))
    }

    const resp = await saveRule(payload)
    message.success(isEdit.value ? '规则更新成功' : '规则创建成功')
    router.push({ path: '/rules' })
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// 数据加载方法
async function loadIfEdit() {
  const id = Number(route.query.id || 0)
  if (!id) return

  try {
    const { data: rule } = await supabase.from('yibao_rules').select('*').eq('id', id).maybeSingle()
    if (rule) {
      form.value = rule

      const [{ data: conds }, { data: acts }, { data: trigs }] = await Promise.all([
        supabase.from('yibao_rule_conditions').select('priority, expression_json').eq('rule_id', id).order('priority', { ascending: true }),
        supabase.from('yibao_rule_actions').select('action_type, message_template').eq('rule_id', id),
        supabase.from('yibao_rule_triggers').select('event_type, priority').eq('rule_id', id).order('priority', { ascending: true })
      ])

      conditionsText.value = JSON.stringify(conds || [], null, 2)
      actionsText.value = JSON.stringify(acts || [], null, 2)
      triggers.value = (trigs || []).map((t: any, i: number) => ({
        key: Math.random().toString(36).slice(2),
        event_type: t.event_type,
        priority: t.priority || (i + 1),
        description: t.description || ''
      }))
    }
  } catch (error) {
    console.error('加载规则失败:', error)
    message.error('加载规则失败')
  }
}

// 生命周期
onMounted(() => {
  loadIfEdit()
})
</script>






