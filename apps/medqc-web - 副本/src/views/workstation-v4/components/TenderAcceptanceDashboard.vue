<template>
  <main class="tender-acceptance-page">
    <section class="acceptance-hero">
      <div>
        <p class="eyebrow">
          TENDER ACCEPTANCE
        </p>
        <h1>投标功能验收看板</h1>
        <p>按条款汇总功能入口、实现状态和仍需生产联调的缺口，所有演示均为只读或草稿/模拟结果。</p>
      </div>
      <div class="summary-card">
        <span>条款总数</span>
        <strong>{{ clauses.length }}</strong>
        <small>implemented {{ implementedCount }} / partial {{ partialCount }}</small>
      </div>
    </section>

    <section class="clause-grid">
      <article
        v-for="clause in clauses"
        :key="clause.id"
        class="clause-card"
      >
        <div class="clause-topline">
          <span>{{ clause.id }}</span>
          <i :class="`status-${clause.status}`">{{ statusLabel[clause.status] }}</i>
        </div>
        <h2>{{ clause.title }}</h2>
        <p>{{ clause.summary }}</p>
        <RouterLink
          :to="clause.entry"
          class="entry-link"
        >
          查看入口
        </RouterLink>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type ClauseStatus = 'implemented' | 'partial'

interface ClauseItem {
  id: string
  title: string
  status: ClauseStatus
  summary: string
  entry: string
}

const statusLabel: Record<ClauseStatus, string> = {
  implemented: '已实现',
  partial: '可演示',
}

const clauses: ClauseItem[] = [
  {
    id: '3.1.1',
    title: '首页自动生成',
    status: 'partial',
    summary: '病案首页、结算清单草稿生成和字段覆盖审查，正式保存仍需人工复核。',
    entry: '/workstation-v4/worklist',
  },
  {
    id: '3.3.1',
    title: '质控规则',
    status: 'partial',
    summary: '首页和结算清单完整性、规范性规则覆盖，支持规则登记和统计。',
    entry: '/workstation-v4/rules',
  },
  {
    id: '3.4.1',
    title: '编码内涵质控',
    status: 'partial',
    summary: '肿瘤病理、病理费、阑尾炎合并编码、冠脉支架附加编码等确定性规则。',
    entry: '/workstation-v4/rules',
  },
  {
    id: '3.4.3',
    title: '诊疗完整性校验',
    status: 'partial',
    summary: '诊断和手术操作时间轴、执行验证、漏填和无依据提示。',
    entry: '/workstation-v4/worklist',
  },
  {
    id: '3.5.1',
    title: '智能编码',
    status: 'implemented',
    summary: 'ICD 诊断、手术操作、医保版和国临版映射查询。',
    entry: '/workstation-v4/icd',
  },
  {
    id: '4.1.2',
    title: '病案问题概览',
    status: 'implemented',
    summary: '按当天问题集中点聚合消息列表，并支持点击定位病历。',
    entry: '/workstation-v4/qc-overview',
  },
  {
    id: '6.1.1',
    title: '自动化入组',
    status: 'partial',
    summary: '入院记录完成后生成只读模拟入组版本，并追踪输入变化。',
    entry: '/workstation-v4/drg/pre',
  },
  {
    id: '6.2.1',
    title: '预入组及修正建议',
    status: 'partial',
    summary: 'DIP/DRG 预入组、未入组修正建议和更优入组选项提示。',
    entry: '/workstation-v4/drg/pre',
  },
  {
    id: '6.2.2',
    title: '分组器本地化适配',
    status: 'partial',
    summary: '地区费率、医院系数、阈值配置和一致率校验。',
    entry: '/workstation-v4/grouper',
  },
  {
    id: '6.2.3',
    title: '医保付费监测',
    status: 'partial',
    summary: '预计支付、实际费用、盈亏、支付率和费用极高/极低组监测。',
    entry: '/workstation-v4/drg/payment',
  },
  {
    id: '6.3.1',
    title: 'DRG/DIP 综合分析',
    status: 'partial',
    summary: '院级、科级、病区、主诊医师组、个人、诊断组和 DRG 维度分析。',
    entry: '/workstation-v4/drg/post',
  },
]

const implementedCount = computed(
  () => clauses.filter((clause) => clause.status === 'implemented').length,
)
const partialCount = computed(() => clauses.filter((clause) => clause.status === 'partial').length)
</script>

<style scoped>
.tender-acceptance-page {
  min-height: 100%;
  background: #f5f9fc;
  color: #0f172a;
  font-family: Inter, 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  padding: 24px;
}

.acceptance-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
  padding: 28px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.acceptance-hero h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  line-height: 36px;
}

.acceptance-hero p {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 22px;
}

.summary-card {
  min-width: 180px;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  background: #eff6ff;
  padding: 18px;
}

.summary-card span,
.summary-card small {
  display: block;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.summary-card strong {
  display: block;
  color: #2563eb;
  font-size: 34px;
  line-height: 42px;
}

.clause-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.clause-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #ffffff;
  padding: 18px;
}

.clause-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.clause-topline i {
  border-radius: 999px;
  font-style: normal;
  padding: 4px 10px;
}

.status-implemented {
  background: #dcfce7;
  color: #047857;
}

.status-partial {
  background: #eaf2ff;
  color: #2563eb;
}

.clause-card h2 {
  margin: 14px 0 8px;
  font-size: 18px;
  font-weight: 800;
}

.clause-card p {
  min-height: 48px;
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 22px;
}

.entry-link {
  display: inline-flex;
  margin-top: 16px;
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

@media (max-width: 1180px) {
  .clause-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .acceptance-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .clause-grid {
    grid-template-columns: 1fr;
  }
}
</style>
