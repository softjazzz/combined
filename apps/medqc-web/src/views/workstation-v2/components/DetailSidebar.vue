<template>
  <aside class="custom-scrollbar w-[198px] min-w-[190px] max-w-[208px] shrink-0 overflow-y-auto border-r border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(247,250,252,0.96))]">
    <div v-if="record" class="flex h-full flex-col">
      <div class="flex-1 px-2 pb-4 pt-3">
        <div class="mb-2 flex items-center justify-between px-1.5">
          <h3 class="m-0 text-[11px] font-black tracking-[0.16em] text-slate-400">&#x75C5;&#x5386;&#x6587;&#x4E66;</h3>
          <SyncOutlined v-if="documentsLoading" spin class="text-[12px] text-blue-500" />
        </div>

        <div class="space-y-1">
          <div
            v-for="doc in documents"
            :key="doc.type + doc.label"
            :class="[
              'group flex items-center justify-between rounded-[12px] border px-2 py-1.5 transition-all duration-150',
              doc.has_content
                ? 'cursor-pointer border-slate-200/70 bg-white/42 hover:border-blue-200 hover:bg-blue-50/62'
                : 'border-transparent bg-white/18 text-slate-300'
            ]"
            @click="doc.has_content && $emit('preview-doc', doc)"
          >
            <span class="flex min-w-0 items-center gap-2">
              <span
                class="flex h-6.5 w-6.5 items-center justify-center rounded-[9px]"
                :class="doc.has_content ? 'bg-blue-50 text-blue-600 group-hover:bg-white' : 'bg-slate-100 text-slate-300'"
              >
                <FileTextOutlined />
              </span>
              <span :class="doc.has_content ? 'truncate text-[12px] font-semibold text-slate-700' : 'truncate text-[12px]'">
                {{ doc.label }}
              </span>
            </span>

            <span v-if="doc.has_content" class="ml-2 flex shrink-0 items-center gap-1.5">
              <span class="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">{{ doc.length }}&#x5B57;</span>
              <EyeOutlined class="text-[11px] text-blue-400" />
            </span>
            <span v-else class="text-[11px] text-slate-200">-</span>
          </div>

          <div v-if="!documentsLoading && documents.length === 0" class="py-4 text-center text-[12px] text-slate-400">
            &#x6682;&#x65E0;&#x75C5;&#x5386;&#x6587;&#x4E66;
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import {
  SyncOutlined,
  FileTextOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import type { PatientRecord, DocItem } from '../types'

defineProps<{
  record: PatientRecord | undefined
  documents: DocItem[]
  documentsLoading: boolean
}>()

defineEmits<{
  'preview-doc': [doc: DocItem]
}>()
</script>
