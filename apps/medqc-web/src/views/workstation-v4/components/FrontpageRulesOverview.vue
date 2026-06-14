<template>
  <section class="rules-workbench">
    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-head">
          <h3>规则覆盖范围</h3>
          <span class="summary-pill">核心字段</span>
        </div>
        <div class="coverage-list">
          <div v-for="item in coverageRows" :key="item.label" class="coverage-row">
            <div>
              <strong>{{ item.label }}</strong>
              <p>{{ item.desc }}</p>
            </div>
            <span class="coverage-badge">{{ item.value }}</span>
          </div>
        </div>
      </article>

      <article class="summary-card">
        <div class="summary-head">
          <h3>执行顺序</h3>
          <span class="summary-pill summary-pill-neutral">统一口径</span>
        </div>
        <ol class="flow-list">
          <li v-for="step in flowSteps" :key="step.index" class="flow-row">
            <span class="flow-index">{{ step.index }}</span>
            <div>
              <strong>{{ step.title }}</strong>
              <p>{{ step.desc }}</p>
            </div>
          </li>
        </ol>
      </article>

      <article class="summary-card">
        <div class="summary-head">
          <h3>优先处理项</h3>
          <span class="summary-pill">高优先级</span>
        </div>
        <div class="watch-list">
          <div v-for="watch in watchItems" :key="watch.label" class="watch-row">
            <div>
              <strong>{{ watch.label }}</strong>
              <p>{{ watch.desc }}</p>
            </div>
            <span class="watch-level">{{ watch.level }}</span>
          </div>
        </div>
      </article>
    </section>

    <section class="table-shell">
      <div class="table-head">
        <div class="table-title-row">
          <h3>首页规则明细</h3>
          <span class="table-chip">按业务影响排序</span>
        </div>
        <div class="table-meta">字段、约束、风险和处理建议统一放在同一张工作表中。</div>
      </div>

      <div class="table-scroll">
        <table class="rules-table">
          <thead>
            <tr>
              <th>编号</th>
              <th>规则名称</th>
              <th>校验字段</th>
              <th>分类</th>
              <th>优先级</th>
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
          <h3>落地口径</h3>
          <span class="table-chip table-chip-neutral">可回填</span>
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
const coverageRows = [
  { label: '基础信息', desc: '病案号、机构、入出院时间、医保类型、科室等基础字段。', value: '18' },
  { label: '诊断映射', desc: '主诊断、其他诊断与 ICD 编码之间保持一致。', value: '11' },
  { label: '手术一致性', desc: '术式名称、编码、日期和术者信息交叉校验。', value: '7' },
  { label: '时序校验', desc: '签名、生成、入出院和回填动作的时间顺序。', value: '6' },
]

const flowSteps = [
  {
    index: '01',
    title: '读取首页基础字段',
    desc: '先校验病案号、机构、科室、入出院时间与住院天数。',
  },
  { index: '02', title: '比对诊断与手术映射', desc: '确保首页字段、编码结果和正文抽取来源一致。' },
  { index: '03', title: '检查签名与回填顺序', desc: '将签名、编码确认和质控回写串成同一条链路。' },
]

const watchItems = [
  {
    label: '主诊断必填且唯一',
    desc: '主诊断不得为空，且应与正文最终诊断和编码结果一致。',
    level: '阻断',
  },
  { label: '入出院时间可回推', desc: '入院时间、出院时间与住院天数之间必须闭环。', level: '高' },
  {
    label: '手术信息同源',
    desc: '术式名称、编码、术者和日期必须来自同一份结构化来源。',
    level: '高',
  },
]

const rules = [
  {
    code: 'FP-01',
    name: '主诊断不可为空且需一致',
    desc: '首页主诊断、正文最终诊断和编码结果需要保持一致。',
    field: '主诊断',
    category: '诊断',
    level: '阻断',
    note: '作为首页生成和编码校验的共同锚点。',
  },
  {
    code: 'FP-02',
    name: '入出院时间顺序成立',
    desc: '入院时间不得晚于出院时间，住院天数必须可回推。',
    field: '入出院时间',
    category: '时序',
    level: '高',
    note: '影响首页、结算和病案统计的一致性。',
  },
  {
    code: 'FP-03',
    name: '手术编码与术式同源',
    desc: '手术名称、编码、日期与术者字段需来自同一份结构化结果。',
    field: '手术信息',
    category: '编码',
    level: '高',
    note: '避免首页、编码和结算使用不同口径。',
  },
  {
    code: 'FP-04',
    name: '签名与回填链路闭环',
    desc: '生成、签名、质控回写和修改动作要具备可追踪顺序。',
    field: '签名链路',
    category: '流程',
    level: '中',
    note: '保证规则结果可回放、可定位、可追责。',
  },
]

const actions = [
  {
    title: '首页抽取完成后先做首轮字段校验',
    desc: '先收完整性，再做映射与时序检查，避免后链路重复返工。',
    status: '建议',
    tags: ['完整性', '首轮校验'],
  },
  {
    title: '主诊断与编码结果保持同一锚点',
    desc: '编码质控和首页校验共用同一主诊断，不允许各自独立提取。',
    status: '强制',
    tags: ['主诊断', '统一来源'],
  },
  {
    title: '回写结果必须带上下文说明',
    desc: '自动回写需说明来源字段、命中规则和处理建议。',
    status: '执行中',
    tags: ['回写', '可解释'],
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
.coverage-list,
.flow-list,
.watch-list,
.action-grid {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}
.coverage-row,
.flow-row,
.watch-row,
.action-card {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  padding: 14px;
}
.flow-row {
  display: flex;
  gap: 12px;
}
.flow-index {
  width: 28px;
  height: 28px;
  border-radius: 12px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.coverage-row strong,
.flow-row strong,
.watch-row strong,
.action-top h4,
.rule-name {
  color: #1d1d1f;
  font-weight: 600;
}
.coverage-row p,
.flow-row p,
.watch-row p,
.action-top p,
.rule-desc,
.rule-note {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 1.65;
}
.coverage-badge,
.watch-level,
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
