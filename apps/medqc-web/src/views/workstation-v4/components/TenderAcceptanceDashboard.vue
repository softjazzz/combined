<template>
  <main class="tender-acceptance-page mq-page">
    <section class="acceptance-hero mq-page-head">
      <div>
        <p class="eyebrow mq-page-eyebrow">功能验收</p>
        <h1 class="mq-page-title">投标功能验收看板</h1>
        <p>按条款汇总功能入口、实现状态和仍需生产联调的缺口，所有演示均为只读或草稿/模拟结果。</p>
      </div>
      <div class="summary-card mq-card">
        <span>条款总数</span>
        <strong>{{ clauses.length }}</strong>
        <small>已实现 {{ implementedCount }} / 可演示 {{ partialCount }}</small>
      </div>
    </section>

    <section class="clause-grid">
      <article v-for="clause in clauses" :key="clause.id" class="clause-card mq-card">
        <div class="clause-topline">
          <span>{{ clause.id }}</span>
          <i :class="`status-${clause.status}`">{{ statusLabel[clause.status] }}</i>
        </div>
        <h2>{{ clause.title }}</h2>
        <p>{{ clause.summary }}</p>
        <RouterLink :to="clause.entry" class="entry-link"> 查看入口 </RouterLink>
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
    entry: '/workstation-v5/worklist',
  },
  {
    id: '3.3.1',
    title: '质控规则',
    status: 'partial',
    summary: '首页和结算清单完整性、规范性规则覆盖，支持规则登记和统计。',
    entry: '/workstation-v5/rules',
  },
  {
    id: '3.4.1',
    title: '编码内涵质控',
    status: 'partial',
    summary: '肿瘤病理、病理费、阑尾炎合并编码、冠脉支架附加编码等确定性规则。',
    entry: '/workstation-v5/rules',
  },
  {
    id: '3.4.3',
    title: '诊疗完整性校验',
    status: 'partial',
    summary: '诊断和手术操作时间轴、执行验证、漏填和无依据提示。',
    entry: '/workstation-v5/worklist',
  },
  {
    id: '3.5.1',
    title: '智能编码',
    status: 'implemented',
    summary: 'ICD 诊断、手术操作、医保版和国临版映射查询。',
    entry: '/workstation-v5/icd',
  },
  {
    id: '4.1.2',
    title: '病案问题概览',
    status: 'implemented',
    summary: '按当天问题集中点聚合消息列表，并支持点击定位病历。',
    entry: '/workstation-v5/qc-overview',
  },
  {
    id: '6.1.1',
    title: '自动化入组',
    status: 'partial',
    summary: '入院记录完成后生成只读模拟入组版本，并追踪输入变化。',
    entry: '/workstation-v5/drg/pre',
  },
  {
    id: '6.2.1',
    title: '预入组及修正建议',
    status: 'partial',
    summary: 'DIP/DRG 预入组、未入组修正建议和更优入组选项提示。',
    entry: '/workstation-v5/drg/pre',
  },
  {
    id: '6.2.2',
    title: '分组器本地化适配',
    status: 'partial',
    summary: '地区费率、医院系数、阈值配置和一致率校验。',
    entry: '/workstation-v5/grouper',
  },
  {
    id: '6.2.3',
    title: '医保付费监测',
    status: 'partial',
    summary: '预计支付、实际费用、盈亏、支付率和费用极高/极低组监测。',
    entry: '/workstation-v5/drg/payment',
  },
  {
    id: '6.3.1',
    title: 'DRG/DIP 综合分析',
    status: 'partial',
    summary: '院级、科级、病区、主诊医师组、个人、诊断组和 DRG 维度分析。',
    entry: '/workstation-v5/drg/post',
  },
]

const implementedCount = computed(
  () => clauses.filter((clause) => clause.status === 'implemented').length,
)
const partialCount = computed(() => clauses.filter((clause) => clause.status === 'partial').length)
</script>

<style scoped src="../styles/tender-acceptance.css"></style>
