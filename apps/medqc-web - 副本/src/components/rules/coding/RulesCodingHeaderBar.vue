<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-[24px] font-black tracking-tight text-slate-900">
          {{ title }}
        </h2>
        <div
          v-if="subtitle"
          class="mt-1 text-[12px] text-slate-500"
        >
          {{ subtitle }}
        </div>
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
          {{ createButtonText }}
        </a-button>
        <a-button
          :disabled="readonly"
          @click="emit('import-template')"
        >
          {{ importButtonText }}
        </a-button>
        <a-button
          :loading="loading"
          @click="emit('run-preflight')"
        >
          {{ preflightButtonText }}
        </a-button>
        <a-button
          type="primary"
          :disabled="readonly"
          @click="emit('publish')"
        >
          {{ publishButtonText }}
        </a-button>
      </a-space>
    </div>

    <a-input
      :value="searchKeyword"
      class="mt-3"
      allow-clear
      :placeholder="searchPlaceholder"
      @update:value="emit('update:searchKeyword', String($event || ''))"
    />
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    versionLabel: string
    searchKeyword: string
    loading: boolean
    hasPendingChanges: boolean
    readonly: boolean
    searchPlaceholder?: string
    createButtonText?: string
    importButtonText?: string
    preflightButtonText?: string
    publishButtonText?: string
  }>(),
  {
    title: '编码质控规则管理',
    subtitle: '',
    searchPlaceholder: '搜索规则名/编码/条件关键词',
    createButtonText: '新建规则',
    importButtonText: '导入模板',
    preflightButtonText: '运行预检',
    publishButtonText: '发布变更',
  },
)

const emit = defineEmits<{
  'update:searchKeyword': [value: string]
  'create-rule': []
  'import-template': []
  'run-preflight': []
  publish: []
}>()
</script>
