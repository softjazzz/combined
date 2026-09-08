<template>
  <a-button size="small" @click="prepare"> 诊断导包 </a-button>
  <a-modal :open="open" title="诊断包 · 历史受限结果" :width="640" :footer="null" @cancel="close">
    <a-spin :spinning="busy">
      <p class="diagnostic-export__notice">
        仅管理员可导出自己创建的任务。此操作不会重跑质控，也不会修改正式结果。
      </p>
      <a-alert v-if="error" type="warning" :message="error" show-icon />
      <template v-if="prepared">
        <a-alert type="warning" :message="prepared.notice" show-icon />
        <div class="diagnostic-export__scope">
          <section>
            <h3>包含内容</h3>
            <p v-for="item in prepared.included" :key="item">
              {{ item }}
            </p>
          </section>
          <section>
            <h3>未包含内容</h3>
            <p v-for="item in prepared.excluded" :key="item">
              {{ item }}
            </p>
          </section>
        </div>
        <section class="diagnostic-export__preview">
          <h3>当前文案投影预览 · {{ supported.length }} 条可用</h3>
          <p v-if="!supported.length">本次只可检查规则状态清单，没有已支持的文案回放项。</p>
          <div v-for="item in supported" :key="item.rule_id">
            <span>{{ item.rule_id }}</span>
            <p>{{ item.current_findings }}</p>
          </div>
        </section>
        <p class="diagnostic-export__notice">
          预览保留 5 分钟，服务重启后失效。包内不含患者身份、病历正文或模型原文。
        </p>
        <a-checkbox v-model:checked="confirmed">
          已了解缺失证据及回放限制，确认下载此预览对应的包
        </a-checkbox>
      </template>
      <div class="diagnostic-export__actions">
        <a-button @click="close"> 取消 </a-button>
        <a-button v-if="error && !prepared" :disabled="busy" @click="prepare"> 重新准备 </a-button>
        <a-button type="primary" :disabled="!prepared || !confirmed || busy" @click="download">
          下载诊断包
        </a-button>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import {
  discardDiagnostic,
  downloadDiagnostic,
  prepareDiagnostic,
  type DiagnosticPreparation,
  type DiagnosticSelection,
} from '@/services/qc-diagnostics-service'

const props = defineProps<{ selection: DiagnosticSelection }>()
const open = ref(false)
const busy = ref(false)
const confirmed = ref(false)
const error = ref('')
const prepared = ref<DiagnosticPreparation | null>(null)
const supported = computed(
  () => prepared.value?.preview.results.filter((item) => item.supported) ?? [],
)
let sequence = 0

function discard(token: string) {
  void discardDiagnostic(token).catch(() => {
    /* 服务端有效期仍会限制下载。 */
  })
}

function close() {
  sequence += 1
  if (prepared.value) discard(prepared.value.token)
  prepared.value = null
  confirmed.value = false
  busy.value = false
  error.value = ''
  open.value = false
}

async function prepare() {
  if (busy.value) return
  close()
  open.value = true
  busy.value = true
  const request = sequence
  try {
    const result = await prepareDiagnostic({ ...props.selection })
    if (request !== sequence) {
      discard(result.token)
      return
    }
    prepared.value = result
  } catch {
    if (request === sequence)
      error.value = '无法准备诊断包。请确认拥有该任务权限，且当前结果未更新。'
  } finally {
    if (request === sequence) busy.value = false
  }
}

async function download() {
  if (!prepared.value || !confirmed.value || busy.value) return
  const request = sequence
  busy.value = true
  error.value = ''
  try {
    const blob = await downloadDiagnostic(prepared.value.token)
    if (request === sequence) downloadBlob(blob, 'qc-diagnostic-history.zip')
  } catch {
    if (request === sequence) error.value = '下载失败或预览已过期，请关闭后重新准备。'
  } finally {
    if (request === sequence) busy.value = false
  }
}

watch(
  () => [
    props.selection.job_id,
    props.selection.record_ref,
    props.selection.institute_id,
    props.selection.patient_id,
    props.selection.visit_id,
  ],
  close,
)
onBeforeUnmount(close)
</script>

<style scoped>
.diagnostic-export__notice {
  margin: 12px 0;
  color: var(--workstation-text-secondary, #64748b);
  font-size: 13px;
  line-height: 1.65;
}
.diagnostic-export__scope {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin: 16px 0;
}
h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}
.diagnostic-export__scope p,
.diagnostic-export__preview p {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.65;
}
.diagnostic-export__preview {
  padding: 14px;
  background: #f5f5f7;
  border-radius: 8px;
  max-height: 220px;
  overflow: auto;
}
.diagnostic-export__preview span {
  color: #64748b;
  font-size: 12px;
}
.diagnostic-export__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>
