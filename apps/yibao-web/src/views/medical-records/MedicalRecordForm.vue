<template>
  <BasicLayout>
    <div class="min-h-screen bg-gray-50 p-8">
      <!-- 页面标题 -->
      <div class="mb-8">
        <div class="bg-gradient-to-r from-blue-500 via-indigo-600 to-purple-600 text-white p-6 rounded-2xl shadow-lg">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20">
              <FileTextOutlined class="text-xl text-white" />
            </div>
            <div>
              <h1 class="text-2xl font-bold">{{ isEdit ? '编辑测试病历' : '新建测试病历' }}</h1>
              <p class="text-blue-100">创建或编辑医保质控测试病历数据</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 表单内容 -->
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
        <a-form
          :model="formData"
          :rules="rules"
          layout="vertical"
          @finish="handleSubmit"
        >
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- 基本信息 -->
            <div class="space-y-4">
              <h3 class="text-lg font-semibold text-gray-800 mb-4">基本信息</h3>
              
              <a-form-item label="病历名称" name="name" required>
                <a-input v-model:value="formData.name" placeholder="请输入病历名称" />
              </a-form-item>

              <a-form-item label="患者姓名" name="patient_name" required>
                <a-input v-model:value="formData.patient_name" placeholder="请输入患者姓名" />
              </a-form-item>

              <a-form-item label="患者ID" name="patient_id" required>
                <a-input v-model:value="formData.patient_id" placeholder="请输入患者ID" />
              </a-form-item>

              <a-form-item label="科室" name="department" required>
                <a-select v-model:value="formData.department" placeholder="请选择科室">
                  <a-select-option value="内科">内科</a-select-option>
                  <a-select-option value="外科">外科</a-select-option>
                  <a-select-option value="外二科">外二科</a-select-option>
                  <a-select-option value="儿科">儿科</a-select-option>
                  <a-select-option value="妇产科">妇产科</a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="记录类型" name="record_type" required>
                <a-select v-model:value="formData.record_type" placeholder="请选择记录类型">
                  <a-select-option value="门诊记录">门诊记录</a-select-option>
                  <a-select-option value="住院记录">住院记录</a-select-option>
                  <a-select-option value="手术记录">手术记录</a-select-option>
                  <a-select-option value="检查记录">检查记录</a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="疾病类型" name="disease_type" required>
                <a-select v-model:value="formData.disease_type" placeholder="请选择疾病类型">
                  <a-select-option value="心血管疾病">心血管疾病</a-select-option>
                  <a-select-option value="呼吸系统">呼吸系统</a-select-option>
                  <a-select-option value="消化系统">消化系统</a-select-option>
                  <a-select-option value="外科疾病">外科疾病</a-select-option>
                  <a-select-option value="其他">其他</a-select-option>
                </a-select>
              </a-form-item>
            </div>

            <!-- 医保信息 -->
            <div class="space-y-4">
              <h3 class="text-lg font-semibold text-gray-800 mb-4">医保信息</h3>
              
              <a-form-item label="医保类型" name="medical_insurance_type">
                <a-select v-model:value="formData.medical_insurance_type" placeholder="请选择医保类型">
                  <a-select-option value="职工医保">职工医保</a-select-option>
                  <a-select-option value="居民医保">居民医保</a-select-option>
                  <a-select-option value="新农合">新农合</a-select-option>
                  <a-select-option value="自费">自费</a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="费用金额" name="cost_amount">
                <a-input-number 
                  v-model:value="formData.cost_amount" 
                  placeholder="请输入费用金额"
                  :min="0"
                  :precision="2"
                  style="width: 100%"
                />
              </a-form-item>

              <a-form-item label="违规风险等级" name="violation_risk">
                <a-select v-model:value="formData.violation_risk" placeholder="请选择风险等级">
                  <a-select-option value="low">低风险</a-select-option>
                  <a-select-option value="medium">中风险</a-select-option>
                  <a-select-option value="high">高风险</a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="复杂度等级" name="complexity_level" required>
                <a-select v-model:value="formData.complexity_level" placeholder="请选择复杂度">
                  <a-select-option value="简单">简单</a-select-option>
                  <a-select-option value="中等">中等</a-select-option>
                  <a-select-option value="复杂">复杂</a-select-option>
                  <a-select-option value="极复杂">极复杂</a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item label="预期评分" name="expected_score">
                <a-input-number 
                  v-model:value="formData.expected_score" 
                  placeholder="请输入预期评分"
                  :min="0"
                  :max="100"
                  style="width: 100%"
                />
              </a-form-item>

              <a-form-item label="标签" name="tags">
                <a-select
                  v-model:value="formData.tags"
                  mode="tags"
                  placeholder="请输入标签"
                  style="width: 100%"
                >
                  <a-select-option value="测试">测试</a-select-option>
                  <a-select-option value="心血管">心血管</a-select-option>
                  <a-select-option value="住院">住院</a-select-option>
                  <a-select-option value="门诊">门诊</a-select-option>
                  <a-select-option value="手术">手术</a-select-option>
                </a-select>
              </a-form-item>
            </div>
          </div>

          <!-- 病历内容 -->
          <div class="mt-8">
            <h3 class="text-lg font-semibold text-gray-800 mb-4">病历内容</h3>
            <a-form-item label="病历详细内容" name="content" required>
              <a-textarea
                v-model:value="formData.content"
                placeholder="请输入病历详细内容..."
                :rows="10"
                show-count
                :maxlength="5000"
              />
            </a-form-item>
          </div>

          <!-- 操作按钮 -->
          <div class="flex justify-end gap-4 mt-8 pt-6 border-t border-gray-200">
            <a-button size="large" @click="handleCancel">
              取消
            </a-button>
            <a-button size="large" @click="handleSaveDraft">
              保存草稿
            </a-button>
            <a-button type="primary" size="large" html-type="submit" :loading="submitting">
              {{ isEdit ? '更新病历' : '创建病历' }}
            </a-button>
          </div>
        </a-form>
      </div>
    </div>
  </BasicLayout>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import BasicLayout from '@/layouts/BasicLayout.vue'
import { FileTextOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()

// 判断是否为编辑模式
const isEdit = ref(!!route.params.id)
const submitting = ref(false)

// 表单数据
const formData = reactive({
  name: '',
  patient_name: '',
  patient_id: '',
  department: '',
  record_type: '',
  disease_type: '',
  complexity_level: '',
  medical_insurance_type: '',
  cost_amount: undefined,
  violation_risk: '',
  expected_score: undefined,
  tags: [],
  content: ''
})

// 表单验证规则
const rules = {
  name: [{ required: true, message: '请输入病历名称', trigger: 'blur' }],
  patient_name: [{ required: true, message: '请输入患者姓名', trigger: 'blur' }],
  patient_id: [{ required: true, message: '请输入患者ID', trigger: 'blur' }],
  department: [{ required: true, message: '请选择科室', trigger: 'change' }],
  record_type: [{ required: true, message: '请选择记录类型', trigger: 'change' }],
  disease_type: [{ required: true, message: '请选择疾病类型', trigger: 'change' }],
  complexity_level: [{ required: true, message: '请选择复杂度等级', trigger: 'change' }],
  content: [{ required: true, message: '请输入病历内容', trigger: 'blur' }]
}

// 方法
async function handleSubmit() {
  submitting.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    message.success(isEdit.value ? '病历更新成功' : '病历创建成功')
    router.push('/medical-records')
  } catch (error) {
    message.error('操作失败，请重试')
  } finally {
    submitting.value = false
  }
}

function handleSaveDraft() {
  message.info('草稿保存功能开发中...')
}

function handleCancel() {
  router.back()
}

// 如果是编辑模式，加载病历数据
async function loadRecordData() {
  if (isEdit.value) {
    try {
      // 模拟加载数据
      await new Promise(resolve => setTimeout(resolve, 500))
      
      // 模拟数据
      Object.assign(formData, {
        name: '张伟住院病历',
        patient_name: '张伟',
        patient_id: 'P001',
        department: '外二科',
        record_type: '住院记录',
        disease_type: '心血管疾病',
        complexity_level: '中等',
        medical_insurance_type: '职工医保',
        cost_amount: 15680.50,
        violation_risk: 'low',
        expected_score: 90,
        tags: ['心血管', '住院'],
        content: '患者张伟，男，45岁，因胸痛3天入院...'
      })
    } catch (error) {
      message.error('加载病历数据失败')
    }
  }
}

onMounted(() => {
  loadRecordData()
})
</script>

<style scoped>
/* 自定义样式 */
</style>
