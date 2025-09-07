<template>
  <BasicLayout>
    <div>
      <h3>规则库</h3>
      <RuleTableShell :rows="rows" :columns="columns" :total="total" :page="page" :pageSize="pageSize" @change="onShellChange">
        <template #filters>
          <a-space>
            <a-input v-model:value="keyword" placeholder="搜索规则名称/编码" style="width:260px;" />
            <a-select v-model:value="enabled" style="width:140px;" :options="enabledOptions" allowClear placeholder="启用状态" />
            <a-button type="primary" @click="load">查询</a-button>
          </a-space>
        </template>
      </RuleTableShell>
    </div>
  </BasicLayout>
  </template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref, onMounted } from 'vue'
import { supabase } from '@/lib/supabase'
import { buildQuery, query } from '@health-qc/web-utils'
import { RuleTableShell } from '@health-qc/ui-qc'

const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const enabled = ref<any>(undefined)

const enabledOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false }
]

const columns = [
  { title: 'ID', dataIndex: 'id' },
  { title: '编码', dataIndex: 'code' },
  { title: '名称', dataIndex: 'name' },
  { title: '类型', dataIndex: 'rule_type' },
  { title: '严重级', dataIndex: 'severity' },
  { title: '启用', dataIndex: 'enabled' }
]

async function load() {
  const base = supabase.from('yibao_rules').select('*', { count: 'exact' })
  const filters: Record<string, any> = {}
  if (keyword.value) filters['name'] = `%${keyword.value}%`
  if (enabled.value !== undefined) filters['enabled'] = enabled.value
  const q = buildQuery(base, { page: page.value, pageSize: pageSize.value, sortBy: 'id', sortOrder: 'desc', filters })
  const res = await query(() => q)
  if (res.success) {
    rows.value = Array.isArray(res.data) ? res.data : []
    total.value = res.count || 0
  }
}

function onTableChange(p: any) {
  page.value = p.current
  pageSize.value = p.pageSize
  load()
}

function onShellChange(p: any) {
  page.value = p.page
  pageSize.value = p.pageSize
  load()
}

onMounted(load)
</script>


