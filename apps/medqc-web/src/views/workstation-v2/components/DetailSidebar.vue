<template>
  <aside
    class="custom-scrollbar w-[194px] min-w-[184px] max-w-[204px] shrink-0 overflow-y-auto border-r border-slate-200/70 bg-[linear-gradient(180deg,rgba(247,251,255,0.94),rgba(240,247,255,0.98))]"
  >
    <div
      v-if="record"
      class="flex h-full flex-col"
    >
      <div class="flex-1 px-2.5 pb-4 pt-3">
        <div class="mb-3 flex items-center justify-between px-1">
          <h3 class="m-0 text-[11px] font-black tracking-[0.16em] text-sky-700/75">
            &#x75C5;&#x5386;&#x6587;&#x4E66;
          </h3>
          <SyncOutlined
            v-if="documentsLoading"
            spin
            class="text-[12px] text-sky-600"
          />
        </div>

        <div class="space-y-1">
          <div
            v-for="doc in documents"
            :key="doc.type + doc.label"
            :class="[
              'group relative flex items-center justify-between rounded-[10px] border px-2 py-1.5 transition-all duration-150',
              doc.has_content
                ? isActive(doc)
                  ? 'cursor-pointer border-sky-200 bg-white text-sky-800 shadow-[0_6px_14px_rgba(14,165,233,0.12)]'
                  : 'cursor-pointer border-transparent bg-transparent hover:border-sky-100 hover:bg-white/75'
                : 'border-transparent bg-transparent text-slate-300',
            ]"
            @click="doc.has_content && $emit('preview-doc', doc)"
          >
            <span
              v-if="doc.has_content"
              class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r-full transition-all duration-150"
              :class="isActive(doc) ? 'bg-sky-500' : 'bg-transparent group-hover:bg-sky-300'"
            />
            <span class="flex min-w-0 items-center gap-2">
              <span
                class="flex h-6 w-6 items-center justify-center rounded-[8px]"
                :class="
                  doc.has_content
                    ? isActive(doc)
                      ? 'bg-sky-100 text-sky-700'
                      : 'bg-slate-100 text-blue-600 group-hover:bg-blue-50'
                    : 'bg-slate-100 text-slate-300'
                "
              >
                <FileTextOutlined />
              </span>
              <span
                :class="
                  doc.has_content
                    ? isActive(doc)
                      ? 'truncate text-[12px] font-bold text-sky-800'
                      : 'truncate text-[12px] font-semibold text-slate-700'
                    : 'truncate text-[12px]'
                "
              >
                {{ doc.label }}
              </span>
            </span>

            <span
              v-if="doc.has_content"
              class="ml-2 flex shrink-0 items-center gap-1.5"
            >
              <span class="text-[10px] font-semibold text-slate-400">{{ doc.length }}&#x5B57;</span>
              <EyeOutlined class="text-[11px] text-slate-300 group-hover:text-blue-400" />
            </span>
            <span
              v-else
              class="text-[11px] text-slate-200"
            >-</span>
          </div>

          <div
            v-if="!documentsLoading && documents.length === 0"
            class="py-4 text-center text-[12px] text-slate-400"
          >
            &#x6682;&#x65E0;&#x75C5;&#x5386;&#x6587;&#x4E66;
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { SyncOutlined, FileTextOutlined, EyeOutlined } from '@ant-design/icons-vue'
import type { PatientRecord, DocItem } from '../types'

const props = defineProps<{
  record: PatientRecord | undefined
  documents: DocItem[]
  documentsLoading: boolean
  activeDocType?: string
}>()

defineEmits<{
  'preview-doc': [doc: DocItem]
}>()

function isActive(doc: DocItem) {
  return (props.activeDocType || '') === (doc.type || '')
}
</script>
