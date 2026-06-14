<template>
  <section class="rules-workbench">
    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-head">
          <h3>严重度分布</h3>
          <span class="summary-pill">阻断优先</span>
        </div>
        <div class="progress-list">
          <div v-for="item in severities" :key="item.label" class="progress-row">
            <div class="progress-meta">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: item.progress }" />
            </div>
          </div>
        </div>
      </article>

      <article class="summary-card">
        <div class="summary-head">
          <h3>结算控制面</h3>
          <span class="summary-pill summary-pill-neutral">核心环节</span>
        </div>
        <div class="control-list">
          <div v-for="item in controls" :key="item.title" class="control-row">
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.desc }}</p>
            </div>
            <span class="control-badge">{{ item.badge }}</span>
          </div>
        </div>
      </article>

      <article class="summary-card">
        <div class="summary-head">
          <h3>规则关注域</h3>
          <span class="summary-pill">四类规则</span>
        </div>
        <div class="distribution-list">
          <div v-for="item in categories" :key="item.label" class="distribution-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="table-shell">
      <div class="table-head">
        <div class="table-title-row">
          <h3>结算规则明细</h3>
          <span class="table-chip">围绕提交与审核链路</span>
        </div>
        <div class="table-meta">规则、字段、风险和处置建议统一放在同一张表中。</div>
      </div>

      <div class="table-scroll">
        <table class="rules-table">
          <thead>
            <tr>
              <th>编号</th>
              <th>规则名称</th>
              <th>校验对象</th>
              <th>分类</th>
              <th>严重度</th>
              <th>执行说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in rules" :key="rule.code">
              <td>
                <span class="rule-code">{{ rule.code }}</span>
              </td>
              <td>
                <div class="rule-name">
                  {{ rule.name }}
                </div>
                <div class="rule-desc">
                  {{ rule.desc }}
                </div>
              </td>
              <td>
                <span class="pill pill-neutral">{{ rule.field }}</span>
              </td>
              <td>
                <span class="pill pill-neutral">{{ rule.category }}</span>
              </td>
              <td>
                <span class="pill pill-strong">{{ rule.level }}</span>
              </td>
              <td class="rule-note">
                {{ rule.note }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="action-shell">
      <div class="table-head">
        <div class="table-title-row">
          <h3>处理清单</h3>
          <span class="table-chip table-chip-neutral">申报前检查</span>
        </div>
      </div>

      <div class="action-grid">
        <article v-for="item in actions" :key="item.title" class="action-card">
          <div class="action-top">
            <div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.desc }}</p>
            </div>
            <span class="action-status">{{ item.status }}</span>
          </div>
          <div class="action-tags">
            <span v-for="tag in item.tags" :key="tag">{{ tag }}</span>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
const severities = [
  { label: '阻断', value: '52', progress: '48%' },
  { label: '警告', value: '55', progress: '52%' },
]

const controls = [
  {
    title: '首页与结算同源',
    desc: '主诊断、手术、费用归属和首页核心字段必须共用同一来源。',
    badge: '必检',
  },
  {
    title: '费用结构完整',
    desc: '药品、耗材、检查、治疗和床位费用需要完整归类。',
    badge: '重点',
  },
  {
    title: '申报顺序闭环',
    desc: '生成、审核、提交和退回动作要形成完整时间链。',
    badge: '流程',
  },
]

const categories = [
  { label: '完整性', value: '41' },
  { label: '规范性', value: '24' },
  { label: '合理性', value: '40' },
  { label: '逻辑质控', value: '2' },
]

const rules = [
  {
    code: 'ST-01',
    name: '首页诊断与结算主诊断一致',
    desc: '首页主诊断、结算主诊断与编码结果必须保持同一口径。',
    field: '主诊断',
    category: '完整性',
    level: '阻断',
    note: '作为结算可提交的首要判断条件。',
  },
  {
    code: 'ST-02',
    name: '费用分类归集完整',
    desc: '药品、耗材、检查、治疗、床位等费用项目不得缺项。',
    field: '费用结构',
    category: '规范性',
    level: '阻断',
    note: '直接影响医保申报与费用审计。',
  },
  {
    code: 'ST-03',
    name: '申报链路时间顺序成立',
    desc: '生成、审核、提交与退回状态必须可按顺序追溯。',
    field: '申报时间链',
    category: '逻辑质控',
    level: '高',
    note: '避免清单已提交但状态链不完整。',
  },
  {
    code: 'ST-04',
    name: '清单编码映射一致',
    desc: 'ICD 编码与医保映射结果需要在清单侧正确落位。',
    field: '编码映射',
    category: '合理性',
    level: '高',
    note: '避免首页、编码和结算三套结果互相冲突。',
  },
]

const actions = [
  {
    title: '先核口径，再审费用',
    desc: '先收主诊断和手术口径，再查看费用结构与分类完整性。',
    status: '建议',
    tags: ['主诊断', '手术口径'],
  },
  {
    title: '申报前统一跑清单链路校验',
    desc: '生成、审核、提交和退回动作链需一次性核通。',
    status: '强制',
    tags: ['申报链路', '状态同步'],
  },
  {
    title: '未通过项保留来源说明',
    desc: '结算质控问题应保留命中规则、原始字段和建议动作。',
    status: '执行中',
    tags: ['可追溯', '建议动作'],
  },
]
</script>

<style scoped>
.rules-workbench {
  display: grid;
  gap: 16px;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}
.summary-card,
.table-shell,
.action-shell {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  padding: 16px;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.summary-card:hover,
.table-shell:hover,
.action-shell:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.summary-head,
.table-head,
.action-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.summary-head h3,
.table-title-row h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: #1d1d1f;
}
.table-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.summary-pill,
.table-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
  font-size: 11px;
  font-weight: 600;
}
.summary-pill-neutral,
.table-chip-neutral {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}
.progress-list,
.control-list,
.distribution-list,
.action-grid {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}
.progress-row,
.control-row,
.distribution-row,
.action-card {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  padding: 14px;
}
.progress-meta,
.distribution-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
.progress-meta strong,
.distribution-row strong,
.control-row strong,
.action-top h4,
.rule-name {
  color: #1d1d1f;
  font-weight: 600;
}
.progress-track {
  margin-top: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: #0066cc;
}
.control-row p,
.action-top p,
.rule-desc,
.rule-note {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 1.65;
}
.control-badge,
.action-status {
  display: inline-flex;
  align-items: center;
  height: 28px;
  border-radius: 999px;
  padding: 0 10px;
  white-space: nowrap;
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
  font-size: 11px;
  font-weight: 600;
}
.table-meta {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-weight: 600;
}
.table-scroll {
  margin-top: 14px;
  overflow-x: auto;
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.9);
}
.rules-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  text-align: left;
}
.rules-table thead th {
  padding: 13px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.025);
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
}
.rules-table tbody td {
  padding: 15px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  vertical-align: top;
}
.rules-table tbody tr {
  transition: background-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.rules-table tbody tr:hover {
  background: rgba(0, 102, 204, 0.045);
}
.rule-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: rgba(29, 29, 31, 0.42);
  font-size: 12px;
  font-weight: 600;
}
.pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
}
.pill-neutral {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}
.pill-strong {
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
}
.action-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.action-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.action-tags span {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
  font-size: 11px;
  font-weight: 600;
}
@media (max-width: 1180px) {
  .summary-grid,
  .action-grid {
    grid-template-columns: 1fr;
  }
}
</style>
