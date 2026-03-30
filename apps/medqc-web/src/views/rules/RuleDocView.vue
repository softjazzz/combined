<template>
  <div class="rule-doc-view">
    <a-card
      title="质控点说明（泸县33条规则逻辑总览）"
      :bordered="false"
    >
      <a-table
        :data-source="ruleDocRows"
        :columns="ruleDocColumns"
        class="rule-doc-table"
        :pagination="{
          pageSize: 10,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '33', '50'],
          showTotal: (total: number) => `共 ${total} 条质控点`,
        }"
        size="small"
        row-key="rule_id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <a-tag color="blue">
              {{ record.rule_id }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'name'">
            <span class="rule-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'description'">
            <a-typography-paragraph :ellipsis="{ rows: 3, expandable: true }">
              {{ record.description }}
            </a-typography-paragraph>
          </template>
          <template v-else-if="column.key === 'check_points'">
            <a-typography-paragraph :ellipsis="{ rows: 5, expandable: true }">
              {{ record.check_points || '（提示词中未单独标注【检查要点】）' }}
            </a-typography-paragraph>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { Typography } from 'ant-design-vue'

interface SichuanQCRule {
  rule_id?: string
  rule_code?: string
  name: string
  description?: string
  custom_prompt?: string
}

const allRules = ref<SichuanQCRule[]>([])

// 从 custom_prompt 中提取【检查要点】段落
const extractCheckPoints = (prompt?: string): string => {
  if (!prompt) return ''
  const marker = '【检查要点】'
  const start = prompt.indexOf(marker)
  if (start === -1) return ''
  const after = prompt.slice(start + marker.length)
  const nextHeaderIndex = after.indexOf('【')
  const section = nextHeaderIndex === -1 ? after : after.slice(0, nextHeaderIndex)
  return section.trim()
}

const ruleDocColumns = [
  {
    title: '质控点编号',
    dataIndex: 'rule_id',
    key: 'rule_id',
    width: 110,
    fixed: 'left',
  },
  {
    title: '质控点名称',
    dataIndex: 'name',
    key: 'name',
    width: 260,
  },
  {
    title: '质控点描述',
    dataIndex: 'description',
    key: 'description',
    width: 360,
  },
  {
    title: '检查要点',
    dataIndex: 'check_points',
    key: 'check_points',
  },
]

const ruleDocRows = computed(() =>
  allRules.value
    // 仅展示 LX- 开头的泸县33条规则，排除扩展规则（LXE-）
    .filter((rule) => {
      const id = (rule.rule_id || rule.rule_code || '').toUpperCase()
      return id.startsWith('LX-') && !id.startsWith('LXE-')
    })
    .map((rule) => ({
      rule_id: rule.rule_id || rule.rule_code,
      name: rule.name,
      description: rule.description,
      check_points: extractCheckPoints(rule.custom_prompt),
    })),
)

onMounted(async () => {
  const customRulesModule = await import('../../../backend/app/data/custom_rules_33.json')
  allRules.value = customRulesModule.default as SichuanQCRule[]
})
</script>

<style scoped>
.rule-doc-view {
  padding: 16px;
}

.rule-doc-table :deep(.ant-table-thead > tr > th) {
  font-weight: 600;
}

.rule-name {
  font-weight: 500;
}
</style>
