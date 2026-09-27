<template>
  <a-drawer
    :open="open"
    placement="right"
    width="min(960px, 100vw)"
    :title="drawerTitle"
    :mask-closable="!saving"
    @close="handleClose"
  >
    <a-alert
      type="info"
      show-icon
      class="edit-drawer__notice"
      message="保存后将派生一份新的测试病历，原病历标记为“已被替换”并保留已运行结果，不在原地修改文书。"
    />
    <a-spin :spinning="loading">
      <a-result
        v-if="loadError"
        status="warning"
        :title="loadError"
      />
      <template v-else-if="!loading">
        <a-form layout="vertical">
          <div class="edit-drawer__basics">
            <a-form-item
              label="测试病历名称"
              required
            >
              <a-input v-model:value="caseTitle" />
            </a-form-item>
            <a-form-item
              label="性别"
              required
              :validate-status="sexMissing ? 'error' : ''"
              :help="sourceMissing.sex ? MISSING_HINT : ''"
            >
              <a-select
                v-model:value="sex"
                data-testid="edit-sex"
                placeholder="请选择性别"
                :options="sexOptions"
              />
            </a-form-item>
            <a-form-item
              label="年龄"
              required
              :validate-status="ageMissing ? 'error' : ''"
              :help="sourceMissing.age ? MISSING_HINT : ''"
            >
              <a-input-number
                v-model:value="age"
                data-testid="edit-age"
                :min="0"
                :max="120"
                :precision="0"
                placeholder="岁"
                class="edit-drawer__age"
              />
            </a-form-item>
            <a-form-item
              label="入院时间"
              required
              :validate-status="admissionMissing ? 'error' : ''"
              :help="sourceMissing.admissionTime ? MISSING_HINT : ''"
            >
              <a-input
                v-model:value="admissionTime"
                data-testid="edit-admission-time"
                placeholder="例如 2026-09-01 08:00"
              />
            </a-form-item>
          </div>
        </a-form>
        <a-empty
          v-if="!documents.length"
          description="未读取到文书"
        />
        <a-card
          v-for="document in documents"
          :key="document.key"
          size="small"
          class="edit-drawer__document"
          :class="{ 'edit-drawer__document--disabled': !document.enabled }"
        >
          <template #title>
            <a-input
              v-model:value="document.title"
              size="small"
              class="edit-drawer__title-input"
            />
          </template>
          <template #extra>
            <a-space>
              <span class="edit-drawer__meta">{{ document.document_type }}</span>
              <a-switch
                v-model:checked="document.enabled"
                checked-children="写入"
                un-checked-children="不写入"
              />
            </a-space>
          </template>
          <a-input
            v-model:value="document.record_time"
            size="small"
            addon-before="记录时间"
            class="edit-drawer__time"
          />
          <a-textarea
            v-model:value="document.content"
            :auto-size="{ minRows: 4, maxRows: 16 }"
            :disabled="!document.enabled"
          />
        </a-card>
      </template>
    </a-spin>
    <template #footer>
      <div class="edit-drawer__footer">
        <a-button
          :disabled="saving"
          @click="handleClose"
        >
          取消
        </a-button>
        <a-button
          type="primary"
          :loading="saving"
          data-testid="edit-save"
          :disabled="loading || Boolean(loadError) || missingFields.length > 0"
          @click="handleSave"
        >
          保存为新副本
        </a-button>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  buildTestRecordEditPayload,
  findMissingEditBasics,
  normalizeWallClock,
  loadTestRecordDocuments,
  saveTestRecordEdit,
} from '@/services/test-medical-records'
import type { TestRecordDocumentDraft, TestRecordItem } from '@/types/test-medical-records'

const props = defineProps<{
  open: boolean
  item: TestRecordItem | null
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'saved', newItemId: string): void
}>()

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const caseTitle = ref('')
const MISSING_HINT = '源病历缺少该字段，请填写'
const sex = ref<string | undefined>(undefined)
const age = ref<number | null>(null)
const admissionTime = ref('')
/** 列表返回为 null 的字段：必填、无默认值。 */
const sourceMissing = ref({ sex: false, age: false, admissionTime: false })
const documents = ref<TestRecordDocumentDraft[]>([])

const basics = computed(() => ({
  caseTitle: caseTitle.value,
  sex: sex.value || '',
  age: age.value,
  admissionTime: admissionTime.value,
}))
const missingFields = computed(() => findMissingEditBasics(basics.value))
const sexMissing = computed(() => missingFields.value.includes('性别'))
const ageMissing = computed(() => missingFields.value.includes('年龄'))
const admissionMissing = computed(() => missingFields.value.includes('入院时间'))
const sexOptions = computed(() => {
  const values = ['男', '女']
  if (sex.value && !values.includes(sex.value)) values.push(sex.value)
  return values.map((value) => ({ value, label: value }))
})

function prefillBasics(item: TestRecordItem) {
  caseTitle.value = item.case_title
  sex.value = item.sex || undefined
  age.value = typeof item.age === 'number' ? item.age : null
  // 列表给出的入院时间按墙上时间显示，不做时区换算。
  admissionTime.value = (normalizeWallClock(item.admission_time) || '').replace('T', ' ')
  sourceMissing.value = {
    sex: !item.sex,
    age: typeof item.age !== 'number',
    admissionTime: !normalizeWallClock(item.admission_time),
  }
}

const drawerTitle = computed(() =>
  props.item ? `编辑测试病历：${props.item.case_title || props.item.visit_id}` : '编辑测试病历',
)

async function loadDocuments(item: TestRecordItem) {
  loading.value = true
  loadError.value = ''
  documents.value = []
  prefillBasics(item)
  const result = await loadTestRecordDocuments(item)
  loading.value = false
  if (!result.success || !result.data) {
    loadError.value = result.message || '读取测试病历文书失败'
    return
  }
  documents.value = result.data
}

watch(
  () => [props.open, props.item?.id] as const,
  ([open]) => {
    if (open && props.item) void loadDocuments(props.item)
  },
  { immediate: true },
)

function handleClose() {
  if (saving.value) return
  emit('close')
}

async function handleSave() {
  const item = props.item
  if (!item) return
  let payload
  try {
    payload = buildTestRecordEditPayload(
      item,
      basics.value,
      documents.value,
    )
  } catch (error) {
    message.warning(error instanceof Error ? error.message : '编辑内容不完整')
    return
  }
  saving.value = true
  const result = await saveTestRecordEdit(payload)
  saving.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '保存编辑副本失败')
    return
  }
  message.success('已保存为新的测试病历，原病历已标记为“已被替换”')
  emit('saved', String(result.data.item?.id || ''))
}
</script>

<style scoped>
.edit-drawer__notice {
  margin-bottom: 16px;
}

.edit-drawer__basics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0 16px;
}

.edit-drawer__age {
  width: 100%;
}

.edit-drawer__document {
  margin-bottom: 12px;
}

.edit-drawer__document--disabled {
  opacity: 0.6;
}

.edit-drawer__title-input {
  max-width: 360px;
}

.edit-drawer__meta {
  color: var(--ant-color-text-secondary, #64748b);
  font-size: 12px;
}

.edit-drawer__time {
  max-width: 320px;
  margin-bottom: 8px;
}

.edit-drawer__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
