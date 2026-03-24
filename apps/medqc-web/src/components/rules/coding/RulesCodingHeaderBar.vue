<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-[24px] font-black tracking-tight text-slate-900">
          编码质控规则管理
        </h2>
        <div class="mt-1 flex items-center gap-2 text-[12px] text-slate-500">
          <span>规则集版本：{{ versionLabel }}</span>
          <a-tag
            v-if="hasPendingChanges"
            color="orange"
          >
            有待发布变更
          </a-tag>
        </div>
      </div>
      <a-space wrap>
        <a-button
          :disabled="readonly"
          @click="emit('create-rule')"
        >
          新建规则
        </a-button>
        <a-button
          :disabled="readonly"
          @click="emit('import-template')"
        >
          导入模板
        </a-button>
        <a-button
          :loading="loading"
          @click="emit('run-preflight')"
        >
          运行预检
        </a-button>
        <a-button
          type="primary"
          :disabled="readonly"
          @click="emit('publish')"
        >
          发布变更
        </a-button>
      </a-space>
    </div>

    <a-input
      :value="searchKeyword"
      class="mt-3"
      allow-clear
      placeholder="搜索规则名/编码/条件关键词"
      @update:value="emit('update:searchKeyword', String($event || ''))"
    />
  </section>
</template>

<script setup lang="ts">
defineProps<{
  versionLabel: string
  searchKeyword: string
  loading: boolean
  hasPendingChanges: boolean
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:searchKeyword': [value: string]
  'create-rule': []
  'import-template': []
  'run-preflight': []
  publish: []
}>()
</script>
