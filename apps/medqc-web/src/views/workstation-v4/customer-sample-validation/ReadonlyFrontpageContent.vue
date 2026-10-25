<template>
  <div
    class="readonly-frontpage"
    data-testid="readonly-frontpage"
  >
    <p class="readonly-frontpage-note">
      空缺字段显示“未返回”，不代表临床未填写。
    </p>
    <section
      v-for="group in display.groups"
      :key="group.key"
    >
      <h5>{{ group.label }}</h5>
      <dl class="readonly-frontpage-fields">
        <div
          v-for="field in group.fields"
          :key="field.key"
        >
          <dt>{{ field.label }}</dt>
          <dd :class="{ 'is-missing': field.value === null }">
            {{ field.value ?? '未返回' }}
          </dd>
        </div>
      </dl>
    </section>
    <section
      v-for="item in tables"
      :key="item.key"
    >
      <h5>
        {{ item.label }}<span v-if="item.table.rows.length"> · {{ item.table.rows.length }}条</span>
      </h5>
      <div
        v-if="item.table.rows.length"
        class="readonly-frontpage-table-wrap"
      >
        <table>
          <thead>
            <tr>
              <th
                v-for="column in item.table.columns"
                :key="column.key"
              >
                {{ column.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, index) in item.table.rows"
              :key="index"
            >
              <td
                v-for="column in item.table.columns"
                :key="column.key"
                :class="{ 'is-missing': row[column.key] === null }"
              >
                {{ row[column.key] ?? '未返回' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p
        v-else
        class="is-missing"
      >
        未返回
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FrontpageDisplay } from './types'

const props = defineProps<{ display: FrontpageDisplay }>()
const tables = computed(() => [
  { key: 'diagnoses', label: '首页诊断', table: props.display.diagnoses },
  { key: 'surgeries', label: '手术及操作', table: props.display.surgeries },
])
</script>

<style scoped>
.readonly-frontpage {
  min-width: 0;
  font-size: 13px;
  line-height: 1.7;
}
.readonly-frontpage-note {
  margin: 16px 0 0;
  color: #64748b;
}
section {
  padding: 20px 0;
  border-bottom: 1px solid #edf1f5;
}
section:last-child {
  border-bottom: 0;
}
h5 {
  margin: 0 0 14px;
  color: #1e3a5f;
  font-size: 14px;
  font-weight: 600;
}
h5 span {
  color: #64748b;
  font-size: 12px;
  font-weight: 400;
}
.readonly-frontpage-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 24px;
  margin: 0;
}
.readonly-frontpage-fields > div {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(90px, 40%) minmax(0, 1fr);
  gap: 10px;
}
dt {
  color: #64748b;
}
dd {
  min-width: 0;
  margin: 0;
  color: #172033;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.is-missing {
  color: #94a3b8;
}
.readonly-frontpage-table-wrap {
  max-width: 100%;
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
th,
td {
  min-width: 100px;
  max-width: 300px;
  padding: 10px 12px;
  border-bottom: 1px solid #edf1f5;
  vertical-align: top;
}
th {
  color: #64748b;
  font-weight: 500;
  background: #f5f9fc;
  white-space: nowrap;
}
td {
  color: #172033;
  overflow-wrap: anywhere;
}
@media (max-width: 760px) {
  .readonly-frontpage-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
