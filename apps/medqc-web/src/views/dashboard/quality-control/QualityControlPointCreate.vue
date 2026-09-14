<template>
  <div class="quality-control-point-create">
    <!-- 面包屑导航 -->
    <div class="breadcrumb-nav mb-4">
      <a-breadcrumb>
        <a-breadcrumb-item>
          <router-link to="/dashboard">
            首页
          </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>
          <router-link to="/dashboard/quality-control">
            非编码质控点管理
          </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>新建质控点</a-breadcrumb-item>
      </a-breadcrumb>
    </div>

    <!-- 页面标题 -->
    <div class="page-header mb-6">
      <h2 class="page-title">
        新建质控点
      </h2>
    </div>

    <!-- 步骤指引 -->
    <div class="steps-container mb-8">
      <a-steps
        :current="currentStep"
        class="custom-steps"
      >
        <a-step title="填写信息" />
        <a-step title="配置规则" />
        <a-step title="测试" />
      </a-steps>

      <!-- 下一步按钮 -->
      <div class="step-actions">
        <a-button
          type="primary"
          class="next-btn"
          @click="handleNextStep"
        >
          下一步
        </a-button>
      </div>
    </div>

    <!-- 表单内容 -->
    <div class="form-container">
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
        class="quality-point-form"
      >
        <div class="form-grid">
          <!-- 左列 -->
          <div class="form-column">
            <a-form-item
              label="质控点名称"
              name="name"
              class="required-field"
            >
              <a-input
                v-model:value="formData.name"
                placeholder="请输入，最多100字"
                :maxlength="100"
                show-count
              />
            </a-form-item>

            <a-form-item
              label="质控类型"
              name="type"
              class="required-field"
            >
              <a-select
                v-model:value="formData.type"
                placeholder="请选择"
                allow-clear
              >
                <a-select-option value="规范性">
                  规范性
                </a-select-option>
                <a-select-option value="完整性">
                  完整性
                </a-select-option>
                <a-select-option value="及时性">
                  及时性
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item
              label="质控文书"
              name="document"
              class="required-field"
            >
              <a-select
                v-model:value="formData.document"
                placeholder="请选择"
                allow-clear
              >
                <a-select-option value="入院记录">
                  入院记录
                </a-select-option>
                <a-select-option value="病案首页">
                  病案首页
                </a-select-option>
                <a-select-option value="出院记录">
                  出院记录
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item
              label="质量管理制度"
              name="managementSystem"
            >
              <a-select
                v-model:value="formData.managementSystem"
                placeholder="请选择"
                allow-clear
              >
                <a-select-option value="核心制度">
                  核心制度
                </a-select-option>
                <a-select-option value="一般制度">
                  一般制度
                </a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <!-- 右列 -->
          <div class="form-column">
            <a-form-item
              label="质控大类"
              name="category"
              class="required-field"
            >
              <a-select
                v-model:value="formData.category"
                placeholder="请选择"
                allow-clear
              >
                <a-select-option value="病历书写与管理基本规范">
                  病历书写与管理基本规范
                </a-select-option>
                <a-select-option value="诊疗规范">
                  诊疗规范
                </a-select-option>
                <a-select-option value="医疗安全">
                  医疗安全
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item
              label="核心制度分类"
              name="coreSystemCategory"
            >
              <a-select
                v-model:value="formData.coreSystemCategory"
                placeholder="请选择"
                allow-clear
              >
                <a-select-option value="首诊负责制">
                  首诊负责制
                </a-select-option>
                <a-select-option value="三级查房制">
                  三级查房制
                </a-select-option>
                <a-select-option value="疑难病例讨论制">
                  疑难病例讨论制
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item
              label="质控信息分类"
              name="infoCategory"
            >
              <a-select
                v-model:value="formData.infoCategory"
                placeholder="请选择"
                allow-clear
              >
                <a-select-option value="基础信息">
                  基础信息
                </a-select-option>
                <a-select-option value="诊疗信息">
                  诊疗信息
                </a-select-option>
                <a-select-option value="管理信息">
                  管理信息
                </a-select-option>
              </a-select>
            </a-form-item>
          </div>
        </div>

        <!-- 文本域字段 -->
        <div class="textarea-fields">
          <a-form-item
            label="质控点来源"
            name="source"
          >
            <a-textarea
              v-model:value="formData.source"
              placeholder="请输入内容"
              :rows="4"
              :maxlength="500"
              show-count
            />
          </a-form-item>

          <a-form-item
            label="质控点意义说明"
            name="significance"
          >
            <a-textarea
              v-model:value="formData.significance"
              placeholder="请输入内容"
              :rows="4"
              :maxlength="500"
              show-count
            />
          </a-form-item>

          <a-form-item
            label="质控点错误示例"
            name="errorExample"
          >
            <a-textarea
              v-model:value="formData.errorExample"
              placeholder="请输入内容"
              :rows="4"
              :maxlength="500"
              show-count
            />
          </a-form-item>
        </div>
      </a-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import type { QualityControlPointForm } from '@/types/quality-control'

// 当前步骤
const currentStep = ref(0)

// 表单引用
const formRef = ref<FormInstance>()

// 表单数据
const formData = reactive<QualityControlPointForm>({
  name: '',
  category: '',
  type: '',
  document: '',
  coreSystemCategory: '',
  infoCategory: '',
  managementSystem: '',
  source: '',
  significance: '',
  errorExample: '',
})

// 表单验证规则
const formRules: FormProps['rules'] = {
  name: [
    { required: true, message: '请输入质控点名称', trigger: 'blur' },
    { max: 100, message: '质控点名称不能超过100个字符', trigger: 'blur' },
  ],
  category: [{ required: true, message: '请选择质控大类', trigger: 'change' }],
  type: [{ required: true, message: '请选择质控类型', trigger: 'change' }],
  document: [{ required: true, message: '请选择质控文书', trigger: 'change' }],
}

// 下一步处理
const handleNextStep = async () => {
  try {
    await formRef.value?.validate()
    if (currentStep.value < 2) {
      currentStep.value++
      message.success('信息保存成功，进入下一步')
    }
  } catch (error) {
    message.error('请完善必填信息')
  }
}
</script>

<style scoped lang="less">
.quality-control-point-create {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;

  .breadcrumb-nav {
    :deep(.ant-breadcrumb-link) {
      color: #666666;
      font-size: 14px;
    }

    :deep(.ant-breadcrumb-separator) {
      color: #999999;
    }
  }

  .page-header {
    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #333333;
      margin: 0;
    }
  }

  .steps-container {
    background: #ffffff;
    padding: 32px 48px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    position: relative;

    .custom-steps {
      max-width: 600px;
      margin: 0 auto;

      :deep(.ant-steps-item-title) {
        font-size: 16px;
        font-weight: 500;
      }

      :deep(.ant-steps-item-process .ant-steps-item-icon) {
        background: #2b6cf6;
        border-color: #2b6cf6;
      }
    }

    .step-actions {
      position: absolute;
      top: 32px;
      right: 48px;

      .next-btn {
        background: #2b6cf6;
        border-color: #2b6cf6;
        font-size: 14px;
        height: 36px;
        padding: 0 24px;
        border-radius: 6px;
      }
    }
  }

  .form-container {
    background: #ffffff;
    padding: 32px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

    .quality-point-form {
      .form-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 32px;
        margin-bottom: 24px;
      }

      .form-column {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }

      .textarea-fields {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }

      :deep(.ant-form-item-label) {
        font-size: 14px;
        font-weight: 500;
        color: #333333;

        &::before {
          display: none !important;
        }
      }

      :deep(.required-field .ant-form-item-label::after) {
        content: '*';
        color: #ff4d4f;
        margin-left: 4px;
      }

      :deep(.ant-input),
      :deep(.ant-select-selector),
      :deep(.ant-input-affix-wrapper) {
        border-radius: 6px;
        border: 1px solid #d9d9d9;
        font-size: 14px;

        &:hover {
          border-color: #40a9ff;
        }

        &:focus,
        &.ant-input-focused,
        &.ant-select-focused .ant-select-selector {
          border-color: #2b6cf6;
          box-shadow: 0 0 0 2px rgba(43, 108, 246, 0.2);
        }
      }

      :deep(.ant-input::placeholder),
      :deep(.ant-select-selection-placeholder) {
        color: #bfbfbf;
      }
    }
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .quality-control-point-create {
    padding: 16px;

    .steps-container {
      padding: 24px 16px;

      .step-actions {
        position: static;
        margin-top: 24px;
        text-align: center;
      }
    }

    .form-container {
      padding: 24px 16px;

      .quality-point-form .form-grid {
        grid-template-columns: 1fr;
        gap: 16px;
      }
    }
  }
}
</style>
