<template>
  <div class="import-container">
    <!-- 头部 -->
    <div class="import-header">
      <div class="header-left">
        <h2>
          <CloudUploadOutlined />
          病历数据导入
        </h2>
        <p class="header-desc">
          通过 Excel / CSV 文件批量导入住院病历数据，支持格式校验和错误报告
        </p>
      </div>
      <a-button @click="$router.push('/dashboard/workstation')">
        <ArrowLeftOutlined />
        返回工作站
      </a-button>
    </div>

    <!-- 步骤条 -->
    <a-steps
      :current="currentStep"
      class="import-steps"
    >
      <a-step
        title="上传文件"
        description="选择 Excel/CSV 文件"
      />
      <a-step
        title="格式校验"
        description="检查字段和数据格式"
      />
      <a-step
        title="数据预览"
        description="确认导入内容"
      />
      <a-step
        title="导入完成"
        description="查看导入结果"
      />
    </a-steps>

    <!-- 步骤内容 -->
    <div class="step-content">
      <!-- Step 1: 上传文件 -->
      <div
        v-if="currentStep === 0"
        class="step-upload"
      >
        <div class="upload-area">
          <a-upload-dragger
            name="file"
            accept=".xlsx,.xls,.csv"
            :file-list="fileList"
            :before-upload="handleBeforeUpload"
            @remove="handleRemove"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">
              点击或拖拽 Excel / CSV 文件到此区域
            </p>
            <p class="ant-upload-hint">
              单次最多导入 500 条病历记录
            </p>
          </a-upload-dragger>
        </div>

        <a-divider>或使用模板</a-divider>

        <div class="template-section">
          <a-card
            size="small"
            class="template-card"
            hoverable
            @click="downloadTemplate"
          >
            <template #cover>
              <div class="template-icon">
                <FileExcelOutlined style="font-size: 36px; color: #52c41a" />
              </div>
            </template>
            <a-card-meta
              title="病历导入模板.xlsx"
              description="标准化病历数据模板，包含必填字段说明"
            >
              <template #avatar>
                <DownloadOutlined style="font-size: 20px; color: #0a6cff" />
              </template>
            </a-card-meta>
          </a-card>
        </div>

        <div class="required-fields">
          <h4>必填字段说明（7 个必须字段）</h4>
          <a-table
            :data-source="requiredFields"
            :columns="fieldColumns"
            :pagination="false"
            size="small"
            bordered
          />
        </div>
      </div>

      <!-- Step 2: 格式校验 -->
      <div
        v-if="currentStep === 1"
        class="step-validate"
      >
        <a-spin
          :spinning="validating"
          tip="正在校验数据格式..."
        >
          <div v-if="!validating && validationResult">
            <a-result
              :status="validationResult.errors.length === 0 ? 'success' : 'warning'"
              :title="validationResult.errors.length === 0 ? '格式校验通过' : `发现 ${validationResult.errors.length} 个问题`"
              :sub-title="`共解析 ${validationResult.totalRows} 行数据，${validationResult.validRows} 行有效`"
            >
              <template #extra>
                <a-button
                  v-if="validationResult.errors.length === 0"
                  type="primary"
                  @click="currentStep = 2"
                >
                  继续下一步
                </a-button>
                <a-button
                  v-else
                  type="primary"
                  @click="currentStep = 2"
                >
                  忽略错误继续
                </a-button>
                <a-button @click="currentStep = 0">
                  重新上传
                </a-button>
              </template>
            </a-result>

            <div
              v-if="validationResult.errors.length > 0"
              class="error-list"
            >
              <h4><WarningOutlined style="color: #faad14" /> 错误详情</h4>
              <a-table
                :data-source="validationResult.errors"
                :columns="errorColumns"
                :pagination="{ pageSize: 10 }"
                size="small"
                bordered
              />
            </div>
          </div>
        </a-spin>
      </div>

      <!-- Step 3: 数据预览 -->
      <div
        v-if="currentStep === 2"
        class="step-preview"
      >
        <div class="preview-stats">
          <a-statistic
            title="总记录数"
            :value="previewData.length"
            class="stat-item"
          />
          <a-statistic
            title="涉及科室"
            :value="previewDepts.length"
            class="stat-item"
          />
          <a-statistic
            title="时间范围"
            :value="previewDateRange"
            class="stat-item"
          />
        </div>

        <a-table
          :data-source="previewData"
          :columns="previewColumns"
          :pagination="{ pageSize: 5 }"
          :scroll="{ x: 1200 }"
          size="small"
          bordered
          class="preview-table"
        />

        <div class="preview-actions">
          <a-checkbox v-model:checked="overwriteExisting">
            相同 visit_id 的记录覆盖旧数据（幂等导入）
          </a-checkbox>
        </div>
      </div>

      <!-- Step 4: 导入完成 -->
      <div
        v-if="currentStep === 3"
        class="step-result"
      >
        <a-spin
          :spinning="importing"
          tip="正在导入数据..."
        >
          <a-result
            v-if="!importing && importResult"
            :status="importResult.failCount === 0 ? 'success' : 'warning'"
            :title="`导入完成：${importResult.successCount} 条成功`"
            :sub-title="importResult.failCount > 0 ? `${importResult.failCount} 条失败` : '所有数据已成功导入'"
          >
            <template #extra>
              <a-button
                type="primary"
                @click="$router.push('/dashboard/workstation')"
              >
                前往工作站查看
              </a-button>
              <a-button @click="resetAll">
                继续导入
              </a-button>
            </template>
            <div class="import-detail">
              <a-descriptions
                bordered
                size="small"
                :column="2"
              >
                <a-descriptions-item label="文件名">
                  {{ fileList[0]?.name || '–' }}
                </a-descriptions-item>
                <a-descriptions-item label="导入时间">
                  {{ importResult.importTime }}
                </a-descriptions-item>
                <a-descriptions-item label="成功条数">
                  <span style="color: #52c41a; font-weight: 600">{{ importResult.successCount }}</span>
                </a-descriptions-item>
                <a-descriptions-item label="失败条数">
                  <span :style="{ color: importResult.failCount > 0 ? '#ff4d4f' : '#52c41a', fontWeight: '600' }">
                    {{ importResult.failCount }}
                  </span>
                </a-descriptions-item>
                <a-descriptions-item label="覆盖记录">
                  {{ importResult.overwriteCount }}
                </a-descriptions-item>
                <a-descriptions-item label="新增记录">
                  {{ importResult.newCount }}
                </a-descriptions-item>
              </a-descriptions>
            </div>
          </a-result>
        </a-spin>
      </div>
    </div>

    <!-- 底部操作 -->
    <div
      v-if="currentStep < 3"
      class="import-footer"
    >
      <a-button
        :disabled="currentStep === 0"
        @click="currentStep--"
      >
        上一步
      </a-button>
      <a-button
        v-if="currentStep === 0"
        type="primary"
        :disabled="fileList.length === 0"
        @click="startValidation"
      >
        开始校验
      </a-button>
      <a-button
        v-if="currentStep === 2"
        type="primary"
        @click="startImport"
      >
        <CloudUploadOutlined />
        确认导入 ({{ previewData.length }} 条)
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * DataImportView.vue - 病历数据导入向导
 *
 * 四步流程：上传文件 → 格式校验 → 数据预览 → 导入完成
 * 支持 Excel/CSV 导入，包含必填字段校验和错误报告。
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  CloudUploadOutlined,
  ArrowLeftOutlined,
  InboxOutlined,
  FileExcelOutlined,
  DownloadOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()

// ==================== 状态 ====================
const currentStep = ref(0)
const fileList = ref<any[]>([])
const validating = ref(false)
const importing = ref(false)
const overwriteExisting = ref(true)

// 校验结果
const validationResult = ref<any>(null)

// 预览数据
const previewData = ref<any[]>([])
const previewDepts = computed(() => [...new Set(previewData.value.map(r => r.deptName))])
const previewDateRange = computed(() => {
  if (previewData.value.length === 0) return '–'
  const dates = previewData.value.map(r => r.admissionDate).filter(Boolean).sort()
  return `${dates[0]} ~ ${dates[dates.length - 1]}`
})

// 导入结果
const importResult = ref<any>(null)

// ==================== 表格配置 ====================
const requiredFields = [
  { key: 'patient_id', field: 'patient_id', name: '患者ID', type: '字符串', desc: '唯一标识患者', example: 'P20250001' },
  { key: 'visit_id', field: 'visit_id', name: '就诊ID', type: '字符串', desc: '本次住院唯一标识（幂等键）', example: 'V20250201001' },
  { key: 'name', field: 'name', name: '患者姓名', type: '字符串', desc: '真实姓名', example: '张三丰' },
  { key: 'dept_name', field: 'dept_name', name: '入院科室', type: '字符串', desc: '科室名称', example: '心内科' },
  { key: 'admission_date', field: 'admission_date', name: '入院日期', type: '日期', desc: 'YYYY-MM-DD 格式', example: '2025-02-01' },
  { key: 'record_type', field: 'record_type', name: '文书类型', type: '枚举', desc: 'admission/discharge/progress/surgery', example: 'admission' },
  { key: 'record_content', field: 'record_content', name: '文书内容', type: '文本', desc: '完整的病历文本内容', example: '主诉：胸痛6小时...' },
]

const fieldColumns = [
  { title: '字段名', dataIndex: 'field', width: 140 },
  { title: '中文名', dataIndex: 'name', width: 100 },
  { title: '类型', dataIndex: 'type', width: 80 },
  { title: '说明', dataIndex: 'desc' },
  { title: '示例', dataIndex: 'example', width: 140 },
]

const errorColumns = [
  { title: '行号', dataIndex: 'row', width: 80 },
  { title: '字段', dataIndex: 'field', width: 120 },
  { title: '错误类型', dataIndex: 'type', width: 120 },
  { title: '错误描述', dataIndex: 'message' },
]

const previewColumns = [
  { title: '就诊ID', dataIndex: 'visitId', width: 140, fixed: 'left' as const },
  { title: '患者姓名', dataIndex: 'name', width: 100 },
  { title: '性别', dataIndex: 'sex', width: 60 },
  { title: '年龄', dataIndex: 'age', width: 70 },
  { title: '科室', dataIndex: 'deptName', width: 100 },
  { title: '入院日期', dataIndex: 'admissionDate', width: 120 },
  { title: '主诊断', dataIndex: 'diagnosisMain', ellipsis: true },
  { title: '文书数', dataIndex: 'docCount', width: 80 },
]

// ==================== 方法 ====================
function handleBeforeUpload(file: any) {
  fileList.value = [file]
  return false // 阻止自动上传
}

function handleRemove() {
  fileList.value = []
}

function downloadTemplate() {
  // TODO: 真实下载模板文件
  console.log('下载模板')
}

async function startValidation() {
  currentStep.value = 1
  validating.value = true

  // Mock 校验过程
  await new Promise(resolve => setTimeout(resolve, 2000))

  // Mock 校验结果：模拟8条数据，其中1条有问题
  validationResult.value = {
    totalRows: 8,
    validRows: 7,
    errors: [
      { key: '1', row: 5, field: 'admission_date', type: '格式错误', message: '日期格式应为 YYYY-MM-DD，实际值为 "2025/2/10"' },
    ]
  }

  // 生成预览数据
  previewData.value = [
    { key: '1', visitId: 'V20250301001', name: '刘明华', sex: '男', age: '55岁', deptName: '消化内科', admissionDate: '2025-03-01', diagnosisMain: '消化性溃疡出血', docCount: 3 },
    { key: '2', visitId: 'V20250301002', name: '周芳', sex: '女', age: '38岁', deptName: '妇科', admissionDate: '2025-03-01', diagnosisMain: '子宫肌瘤', docCount: 4 },
    { key: '3', visitId: 'V20250302003', name: '吴强', sex: '男', age: '62岁', deptName: '神经内科', admissionDate: '2025-03-02', diagnosisMain: '脑梗死', docCount: 3 },
    { key: '4', visitId: 'V20250302004', name: '孙丽娟', sex: '女', age: '49岁', deptName: '内分泌科', admissionDate: '2025-03-02', diagnosisMain: '2型糖尿病酮症', docCount: 2 },
    { key: '5', visitId: 'V20250303005', name: '马建军', sex: '男', age: '70岁', deptName: '泌尿外科', admissionDate: '2025-03-03', diagnosisMain: '前列腺增生', docCount: 4 },
    { key: '6', visitId: 'V20250303006', name: '黄秀兰', sex: '女', age: '28岁', deptName: '眼科', admissionDate: '2025-03-03', diagnosisMain: '视网膜脱离', docCount: 3 },
    { key: '7', visitId: 'V20250304007', name: '林志远', sex: '男', age: '43岁', deptName: '骨科', admissionDate: '2025-03-04', diagnosisMain: '腰椎间盘突出症', docCount: 3 },
  ]

  validating.value = false
}

async function startImport() {
  currentStep.value = 3
  importing.value = true

  // Mock 导入过程
  await new Promise(resolve => setTimeout(resolve, 3000))

  importResult.value = {
    successCount: 7,
    failCount: 0,
    overwriteCount: 0,
    newCount: 7,
    importTime: new Date().toLocaleString('zh-CN'),
  }

  importing.value = false
}

function resetAll() {
  currentStep.value = 0
  fileList.value = []
  validationResult.value = null
  previewData.value = []
  importResult.value = null
}
</script>

<style scoped>
.import-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.import-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.import-header h2 {
  margin: 0;
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-desc {
  margin: 4px 0 0;
  color: #888;
  font-size: 13px;
}

.import-steps {
  margin-bottom: 32px;
}

.step-content {
  min-height: 400px;
}

/* Step 1: 上传 */
.upload-area {
  max-width: 600px;
  margin: 0 auto;
}

.template-section {
  display: flex;
  justify-content: center;
  margin: 16px 0;
}

.template-card {
  width: 300px;
  cursor: pointer;
}

.template-icon {
  display: flex;
  justify-content: center;
  padding: 20px 0 8px;
}

.required-fields {
  margin-top: 32px;
}

.required-fields h4 {
  margin-bottom: 12px;
  color: #1a1a1a;
}

/* Step 2: 校验 */
.error-list {
  margin-top: 24px;
}

.error-list h4 {
  margin-bottom: 12px;
}

/* Step 3: 预览 */
.preview-stats {
  display: flex;
  gap: 32px;
  margin-bottom: 20px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.stat-item {
  min-width: 120px;
}

.preview-table {
  margin-bottom: 16px;
}

.preview-actions {
  padding: 12px 0;
}

/* Step 4: 结果 */
.import-detail {
  margin-top: 16px;
}

/* 底部操作 */
.import-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}
</style>
