<template>
  <a-card class="rule-preview-card">
    <template #title>
      <span><FileTextOutlined /> 生成的质控规则</span>
    </template>
    <a-form layout="vertical">
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="规则编号">
            <a-input
              :value="editableRule.rule_code"
              disabled
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            label="规则名称"
            required
          >
            <a-input
              v-model:value="editableRule.name"
              placeholder="请输入规则名称"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="文书类别">
            <a-input v-model:value="editableRule.category" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="缺陷级别">
            <a-input v-model:value="editableRule.defect_level" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="复杂度">
            <a-input v-model:value="editableRule.complexity" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item
        label="规则描述"
        required
      >
        <a-textarea
          v-model:value="editableRule.description"
          :rows="4"
          placeholder="请描述规则的具体要求"
        />
      </a-form-item>

      <a-collapse
        v-model:active-key="activePanels"
        :bordered="false"
        class="rule-collapse"
      >
        <a-collapse-panel key="ruleDetail">
          <template #header>
            <span class="collapse-header">
              <FileSearchOutlined /> 质控规则详情
            </span>
          </template>
          <code-editor
            v-model="editableRule.custom_prompt"
            :rows="12"
          />
        </a-collapse-panel>
      </a-collapse>

      <a-tabs
        v-model:active-key="exampleTab"
        type="card"
        class="example-tabs"
      >
        <a-tab-pane key="positive">
          <template #tab>
            <span><CheckCircleOutlined style="color: #52c41a;" /> 合规示例</span>
          </template>
          <div class="example-content">
            <a-form-item label="示例标题">
              <a-input
                v-model:value="editableRule.positive_example.title"
                placeholder="示例标题"
              />
            </a-form-item>
            <a-form-item label="病历内容">
              <a-textarea
                v-model:value="editableRule.positive_example.content"
                :rows="6"
                placeholder="请输入合规示例的病历内容"
              />
            </a-form-item>
            <a-form-item label="合规说明">
              <a-textarea
                v-model:value="editableRule.positive_example.explanation"
                :rows="3"
                placeholder="说明该示例为何合规"
              />
            </a-form-item>
          </div>
        </a-tab-pane>

        <a-tab-pane key="negative">
          <template #tab>
            <span><ExclamationCircleOutlined style="color: #faad14;" /> 不合规示例</span>
          </template>
          <div class="example-content">
            <a-form-item label="示例标题">
              <a-input
                v-model:value="editableRule.negative_example.title"
                placeholder="示例标题"
              />
            </a-form-item>
            <a-form-item label="病历内容">
              <a-textarea
                v-model:value="editableRule.negative_example.content"
                :rows="6"
                placeholder="请输入不合规示例的病历内容"
              />
            </a-form-item>
            <a-form-item label="不合规说明">
              <a-textarea
                v-model:value="editableRule.negative_example.explanation"
                :rows="3"
                placeholder="说明该示例为何不合规"
              />
            </a-form-item>
          </div>
        </a-tab-pane>
      </a-tabs>

      <div class="actions">
        <a-space>
          <a-button
            type="primary"
            @click="emitSave"
          >
            保存规则
          </a-button>
          <a-tooltip title="请先保存规则后返回规则列表进行质控测试">
            <a-button disabled>
              测试规则
            </a-button>
          </a-tooltip>
          <a-button
            danger
            ghost
            @click="emitRegenerate"
          >
            重新生成
          </a-button>
          <a-button
            type="link"
            @click="restoreOriginal"
          >
            恢复AI版本
          </a-button>
        </a-space>
      </div>
    </a-form>
  </a-card>
</template>

<script setup lang="ts">
import { watch, ref } from 'vue'
import { FileTextOutlined, CheckCircleOutlined, ExclamationCircleOutlined, FileSearchOutlined } from '@ant-design/icons-vue'
import CodeEditor from './CodeEditor.vue'

type RulePayload = Record<string, any>

const props = defineProps<{ rule: RulePayload }>()
const emit = defineEmits<{
  (e: 'save', value: RulePayload): void
  (e: 'regenerate'): void
}>()

const exampleTab = ref('positive')
const activePanels = ref(['ruleDetail'])

const createEditableCopy = (rule: RulePayload): RulePayload => {
  const copy = JSON.parse(JSON.stringify(rule || {}))
  copy.positive_example = copy.positive_example || { title: '', content: '', explanation: '' }
  copy.negative_example = copy.negative_example || { title: '', content: '', explanation: '' }
  return copy
}

const editableRule = ref<RulePayload>(createEditableCopy(props.rule))

watch(
  () => props.rule,
  (newRule) => {
    editableRule.value = createEditableCopy(newRule)
  },
  { deep: true }
)

const emitSave = () => {
  emit('save', createEditableCopy(editableRule.value))
}

const emitRegenerate = () => {
  emit('regenerate')
}

const restoreOriginal = () => {
  editableRule.value = createEditableCopy(props.rule)
}
</script>

<style scoped lang="less">
.rule-preview-card {
  height: 100%;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(43, 108, 246, 0.08), 0 2px 6px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(180deg, #fafcff 0%, #ffffff 100%);
  border: 1px solid #e6f0ff;

  :deep(.ant-card-head) {
    border-bottom: 1px solid #91d5ff;
    font-size: 16px;
    font-weight: 600;
    background: linear-gradient(135deg, #2b6cf6 0%, #69c0ff 50%, #e6f7ff 100%);
    position: relative;
    color: #fff;
  }

  :deep(.ant-card-body) {
    padding: 24px;
  }

  :deep(.ant-form-item) {
    margin-bottom: 20px;
  }

  :deep(.ant-form-item-label > label) {
    font-size: 14px;
    font-weight: 500;
    color: #475569;
  }

  :deep(.ant-input),
  :deep(.ant-input-disabled) {
    font-size: 14px;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    transition: all 0.2s;

    &:hover:not(:disabled) {
      border-color: #94a3b8;
    }

    &:focus {
      border-color: #2b6cf6;
      box-shadow: 0 0 0 2px rgba(43, 108, 246, 0.1);
    }

    &:disabled {
      background: #f8fafc;
      color: #94a3b8;
      cursor: not-allowed;
    }
  }

  :deep(.ant-input-textarea) {
    textarea {
      font-size: 14px;
      line-height: 1.6;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      padding: 10px 12px;
      transition: all 0.2s;

      &:hover {
        border-color: #94a3b8;
      }

      &:focus {
        border-color: #2b6cf6;
        box-shadow: 0 0 0 2px rgba(43, 108, 246, 0.1);
      }
    }
  }

  .rule-collapse {
    margin-bottom: 24px;
    background: transparent;

    :deep(.ant-collapse-item) {
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 0;
    }

    :deep(.ant-collapse-header) {
      background: linear-gradient(135deg, #69c0ff 0%, #bae7ff 50%, #e6f7ff 100%);
      padding: 12px 16px;
      font-size: 14px;
      font-weight: 600;
      color: #003a8c;
      transition: all 0.3s;

      &:hover {
        background: linear-gradient(135deg, #40a9ff 0%, #91d5ff 50%, #d6e4ff 100%);
      }

      .collapse-header {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }

    :deep(.ant-collapse-content) {
      border-top: 1px solid #e2e8f0;

      .ant-collapse-content-box {
        padding: 16px;
      }
    }
  }

  .example-tabs {
    margin-bottom: 24px;

    :deep(.ant-tabs-nav) {
      margin-bottom: 16px;

      .ant-tabs-tab {
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 500;
        border-radius: 8px 8px 0 0;
        transition: all 0.3s;

        &:hover {
          color: #2b6cf6;
        }

        &.ant-tabs-tab-active {
          .ant-tabs-tab-btn {
            color: #2b6cf6;
            font-weight: 600;
          }
        }
      }
    }

    .example-content {
      padding: 16px;
      background: #fafafa;
      border-radius: 8px;

      :deep(.ant-form-item) {
        margin-bottom: 16px;

        &:last-child {
          margin-bottom: 0;
        }
      }
    }
  }

  .actions {
    margin: 24px -24px -24px;
    padding: 16px 24px;
    background: #fafafa;
    border-top: 1px solid #f1f5f9;
    border-radius: 0 0 12px 12px;
    text-align: right;

    :deep(.ant-btn) {
      border-radius: 8px;
      font-weight: 500;
      height: 40px;
      padding: 0 20px;
    }

    :deep(.ant-btn-primary) {
      box-shadow: 0 2px 4px rgba(43, 108, 246, 0.2);

      &:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(43, 108, 246, 0.3);
      }
    }
  }
}
</style>
