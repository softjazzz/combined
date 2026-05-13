<template>
  <a-drawer
    :open="visible"
    :title="null"
    placement="right"
    :width="1460"
    class="qc-review-drawer"
    :destroy-on-close="true"
    @close="handleClose"
  >
    <div class="review-shell">
      <header class="review-summary">
        <div class="review-summary__top">
          <div class="review-summary__identity">
            <div class="review-summary__avatar">
              {{ recordInitial }}
            </div>
            <div class="review-summary__identity-main">
              <div class="review-summary__title-row">
                <h2 class="review-summary__title">
                  病历联审详情
                </h2>
                <span
                  class="review-summary__status"
                  :class="statusClass"
                >
                  <span
                    class="review-summary__status-dot"
                    :class="statusDotClass"
                  />
                  {{ statusText }}
                </span>
              </div>
              <div class="review-summary__patient-row">
                <span class="review-summary__patient-name">{{ record?.patient_name || '-' }}</span>
                <span class="review-summary__patient-meta">病案号：{{ record?.record_id || '-' }}</span>
              </div>
              <div class="review-summary__hint">
                目录按文书类型聚合，再按时间倒序浏览。点击右侧质控问题会联动定位左侧原文段落。
              </div>
            </div>
          </div>
          <div class="review-summary__actions">
            <div class="review-summary__actions-label">
              当前工作区
            </div>
            <div class="review-summary__actions-value">
              联审阅读 / 问题定位
            </div>
          </div>
        </div>
        <div class="review-metrics">
          <div class="review-metric-card">
            <div class="review-metric-card__label">
              科室
            </div>
            <div class="review-metric-card__value">
              {{ record?.department || '-' }}
            </div>
          </div>
          <div class="review-metric-card">
            <div class="review-metric-card__label">
              出院日期
            </div>
            <div class="review-metric-card__value">
              {{ record?.discharge_date || '-' }}
            </div>
          </div>
          <div class="review-metric-card">
            <div class="review-metric-card__label">
              质控得分
            </div>
            <div
              class="review-metric-card__value review-metric-card__value--mono"
              :style="{ color: getScoreColor(record?.score) }"
            >
              {{ record?.score ?? '-' }}
            </div>
          </div>
          <div class="review-metric-card">
            <div class="review-metric-card__label">
              缺陷数
            </div>
            <div class="review-metric-card__value">
              {{ record?.defect_count || 0 }}
            </div>
          </div>
          <div class="review-metric-card">
            <div class="review-metric-card__label">
              文书数量
            </div>
            <div class="review-metric-card__value">
              {{ documentCount }}
            </div>
          </div>
        </div>
      </header>

      <section class="review-workspace">
        <aside class="review-sidebar">
          <div class="review-panel__header review-sidebar__header">
            <div>
              <div class="review-panel__title">
                文书目录
              </div>
              <div class="review-panel__desc">
                按单据类型和时间浏览完整病历。
              </div>
            </div>
          </div>
          <div class="review-sidebar__toolbar">
            <label class="review-sidebar__select-wrap">
              <span class="review-sidebar__select-label">单据范围</span>
              <select
                v-model="sidebarDocFilter"
                class="review-sidebar__select"
              >
                <option
                  v-for="option in sidebarFilterOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
          </div>
          <div class="review-sidebar__list">
            <template v-if="visibleSidebarGroups.length > 0">
              <button
                type="button"
                class="review-tree-node review-tree-node--root"
                :class="{ 'review-tree-node--active': activeDocGroup === 'all' }"
                @click="handleSidebarAllClick"
              >
                <span class="review-tree-node__label">全部</span>
              </button>

              <button
                v-if="fixedFrontpageDoc"
                type="button"
                class="review-tree-node review-tree-node--root"
                :class="{ 'review-tree-node--active': activeDocGroup === 'frontpage' }"
                @click="handleSidebarFrontpageClick"
              >
                <span class="review-tree-node__label">病案首页(临床医生)</span>
              </button>

              <div
                v-for="group in visibleSidebarGroups"
                :key="group.key"
                class="review-tree-group"
              >
                <button
                  type="button"
                  class="review-tree-node"
                  :class="{
                    'review-tree-node--active': activeDocGroup === group.key,
                    'review-tree-node--expanded': isSidebarGroupExpanded(group.key),
                  }"
                  @click="
                    isSidebarGroupExpandable(group)
                      ? handleSidebarGroupHeaderClick(group)
                      : handleSidebarLeafGroupClick(group)
                  "
                >
                  <span
                    v-if="isSidebarGroupExpandable(group)"
                    class="review-tree-node__caret"
                  >
                    {{ isSidebarGroupExpanded(group.key) ? '⌄' : '›' }}
                  </span>
                  <span
                    v-else
                    class="review-tree-node__spacer"
                  />
                  <span class="review-tree-node__label">
                    {{ group.label }}
                  </span>
                </button>

                <div
                  v-if="isSidebarGroupExpandable(group) && isSidebarGroupExpanded(group.key)"
                  class="review-tree-children"
                >
                  <button
                    v-for="doc in getSidebarGroupDocs(group)"
                    :key="doc.doc_key"
                    type="button"
                    class="review-tree-doc"
                    :class="{ 'review-tree-doc--active': activeDocKey === doc.doc_key }"
                    @click="handleSidebarDocClick(group.key, doc)"
                  >
                    <span class="review-tree-doc__date">
                      {{ renderSidebarDocDate(doc) }}
                    </span>
                    <span class="review-tree-doc__title">
                      {{ renderSidebarDocTitle(doc) }}
                    </span>
                  </button>
                </div>
              </div>
            </template>
            <div
              v-else
              class="review-empty review-empty--sidebar"
            >
              <div class="review-empty__title">
                当前分组暂无可展示文书
              </div>
              <div class="review-empty__desc">
                请切换其他文书分组继续查看
              </div>
            </div>
          </div>
        </aside>

        <main class="review-content">
          <div
            v-if="currentDoc || isOrderOverviewActive"
            class="review-panel__header review-content__header"
          >
            <div class="review-content__header-main">
              <div class="review-content__title-row">
                <span class="review-content__type-badge">
                  {{ isOrderOverviewActive ? '医嘱总览' : currentDocTypeLabel }}
                </span>
                <span
                  v-if="!isOrderOverviewActive && currentDocReadableTime"
                  class="review-content__time"
                >记录时间：{{ currentDocReadableTime }}</span>
              </div>
              <h3 class="review-content__title">
                {{ isOrderOverviewActive ? orderOverviewTitle : currentDocTitle }}
              </h3>
              <div
                v-if="isOrderOverviewActive ? orderOverviewMeta : currentDocMeta"
                class="review-content__meta"
              >
                {{ isOrderOverviewActive ? orderOverviewMeta : currentDocMeta }}
              </div>
            </div>
            <div
              v-if="!isOrderOverviewActive && currentDocVisibleFlags.length > 0"
              class="review-content__flags"
            >
              <span
                v-for="flag in currentDocVisibleFlags"
                :key="flag"
                class="review-flag"
              >
                {{ flag }}
              </span>
            </div>
          </div>

          <div class="review-content__body">
            <a-spin :spinning="docLoading">
              <template v-if="isOrderOverviewActive">
                <div
                  v-if="activeReviewIssueSummary"
                  class="review-alert"
                >
                  <div class="review-alert__title">
                    已定位当前质控问题原文
                  </div>
                  <div class="review-alert__desc">
                    {{ activeReviewIssueSummary }}
                  </div>
                </div>

                <div class="review-card order-overview">
                  <div class="order-overview__summary">
                    <div class="order-overview__stat">
                      <span>总医嘱</span>
                      <strong>{{ orderOverviewStats.total }}</strong>
                    </div>
                    <div
                      v-if="orderOverviewStats.temp > 0"
                      class="order-overview__stat"
                    >
                      <span>临时医嘱</span>
                      <strong>{{ orderOverviewStats.temp }}</strong>
                    </div>
                    <div
                      v-if="orderOverviewStats.long > 0"
                      class="order-overview__stat"
                    >
                      <span>长期医嘱</span>
                      <strong>{{ orderOverviewStats.long }}</strong>
                    </div>
                    <div
                      v-if="orderOverviewStats.drug > 0"
                      class="order-overview__stat"
                    >
                      <span>药品医嘱</span>
                      <strong>{{ orderOverviewStats.drug }}</strong>
                    </div>
                    <div
                      v-if="orderOverviewStats.nondrug > 0"
                      class="order-overview__stat"
                    >
                      <span>非药品医嘱</span>
                      <strong>{{ orderOverviewStats.nondrug }}</strong>
                    </div>
                    <div class="order-overview__range">
                      时间范围：{{ orderOverviewTimeRange || '未标记' }}
                    </div>
                  </div>

                  <div class="order-overview__toolbar">
                    <div class="order-overview__filters">
                      <button
                        v-for="option in orderFilterOptions"
                        :key="option.value"
                        type="button"
                        class="order-overview__filter"
                        :class="{
                          'order-overview__filter--active': orderOverviewFilter === option.value,
                        }"
                        @click="orderOverviewFilter = option.value"
                      >
                        {{ option.label }}
                      </button>
                    </div>
                    <input
                      v-model="orderKeyword"
                      class="order-overview__search"
                      type="search"
                      placeholder="搜索医嘱内容、医生或状态"
                    >
                  </div>

                  <div
                    v-if="filteredOrderRows.length > 0"
                    class="order-overview__table-scroll"
                  >
                    <table class="order-overview__table">
                      <thead>
                        <tr>
                          <th>日期/时间</th>
                          <th>医嘱类型</th>
                          <th>医嘱类别</th>
                          <th>医嘱内容</th>
                          <th v-if="showOrderDoseUsageColumn">
                            剂量/频次/用法
                          </th>
                          <th v-if="showOrderStopTimeColumn">
                            停止时间
                          </th>
                          <th v-if="showOrderStatusColumn">
                            状态
                          </th>
                          <th v-if="showOrderDoctorColumn">
                            医生
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="row in filteredOrderRows"
                          :key="row.key"
                          :ref="(el) => setHighlightBlockRef(row.blockKey, el as Element | null)"
                          :class="{
                            'order-overview__row--active': activeHighlightBlockKey === row.blockKey,
                          }"
                        >
                          <td class="order-overview__time">
                            {{ row.time || row.startTime || '-' }}
                          </td>
                          <td>
                            <span class="order-overview__tag">{{ row.orderTypeLabel }}</span>
                          </td>
                          <td>
                            <span class="order-overview__tag order-overview__tag--muted">
                              {{ row.categoryLabel }}
                            </span>
                          </td>
                          <td class="order-overview__content">
                            <span
                              v-html="renderBlockHtml({ key: row.blockKey, text: row.content })"
                            />
                          </td>
                          <td v-if="showOrderDoseUsageColumn">
                            {{ row.doseUsage || '-' }}
                          </td>
                          <td v-if="showOrderStopTimeColumn">
                            {{ row.stopTime || '-' }}
                          </td>
                          <td v-if="showOrderStatusColumn">
                            {{ row.status || '-' }}
                          </td>
                          <td v-if="showOrderDoctorColumn">
                            {{ row.doctor || '-' }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div
                    v-else
                    class="review-empty order-overview__empty"
                  >
                    <div class="review-empty__title">
                      {{ orderRows.length > 0 ? '没有匹配的医嘱' : '暂无医嘱数据' }}
                    </div>
                    <div class="review-empty__desc">
                      {{
                        orderRows.length > 0 ? '请调整筛选或搜索关键词' : '当前病历尚未装配医嘱明细'
                      }}
                    </div>
                  </div>
                </div>
              </template>

              <template v-else-if="currentDoc">
                <div
                  v-if="activeReviewIssueSummary"
                  class="review-alert"
                >
                  <div class="review-alert__title">
                    已定位当前质控问题原文
                  </div>
                  <div class="review-alert__desc">
                    {{ activeReviewIssueSummary }}
                  </div>
                </div>

                <div
                  v-if="
                    currentDocFieldList.length > 0 ||
                      currentDocSectionBlocks.length > 0 ||
                      shouldShowCurrentDocPlainContent
                  "
                  class="review-card review-card--structured"
                >
                  <div class="review-structured-list">
                    <div
                      v-for="field in currentDocFieldList"
                      :key="field.key"
                      class="review-structured-row"
                    >
                      <div class="review-structured-row__label">
                        {{ field.label }}
                      </div>
                      <div class="review-structured-row__content">
                        <div
                          :ref="(el) => setHighlightBlockRef(field.blockKey, el as Element | null)"
                          class="doc-content doc-content--prewrap review-paragraph review-paragraph--inline"
                          :class="{
                            'doc-content--active-highlight':
                              activeHighlightBlockKey === field.blockKey,
                          }"
                          v-html="renderBlockHtml({ key: field.blockKey, text: field.value })"
                        />
                      </div>
                    </div>

                    <template v-if="currentDocSectionBlocks.length > 0">
                      <div
                        v-for="(section, index) in currentDocSectionBlocks"
                        :key="`${section.title}-${index}`"
                        class="review-structured-row"
                      >
                        <div class="review-structured-row__label">
                          {{ section.title }}
                        </div>
                        <div class="review-structured-row__content">
                          <div
                            v-for="block in section.blocks"
                            :key="block.key"
                            :ref="(el) => setHighlightBlockRef(block.key, el as Element | null)"
                            class="doc-content doc-content--prewrap review-paragraph"
                            :class="{
                              'doc-content--active-highlight':
                                activeHighlightBlockKey === block.key,
                            }"
                            v-html="renderBlockHtml(block)"
                          />
                        </div>
                      </div>
                    </template>

                    <div
                      v-else-if="shouldShowCurrentDocPlainContent"
                      class="review-structured-row"
                    >
                      <div class="review-structured-row__label">
                        记录内容
                      </div>
                      <div class="review-structured-row__content">
                        <div
                          v-for="block in currentDocPlainBlocks"
                          :key="block.key"
                          :ref="(el) => setHighlightBlockRef(block.key, el as Element | null)"
                          class="doc-content doc-content--prewrap review-paragraph"
                          :class="{
                            'doc-content--active-highlight': activeHighlightBlockKey === block.key,
                          }"
                          v-html="renderBlockHtml(block)"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-else
                  class="review-empty"
                >
                  <FileTextOutlined class="review-empty__icon" />
                  <div class="review-empty__title">
                    {{ docLoading ? '加载中...' : '当前文书暂无可展示内容' }}
                  </div>
                  <div class="review-empty__desc">
                    可切换其它文书继续查看
                  </div>
                </div>
              </template>

              <div
                v-else
                class="review-empty"
              >
                <FileTextOutlined class="review-empty__icon" />
                <div class="review-empty__title">
                  {{ docLoading ? '加载中...' : '暂无文书内容' }}
                </div>
                <div class="review-empty__desc">
                  当前病历尚未装配可阅读文书
                </div>
              </div>
            </a-spin>
          </div>
        </main>

        <aside class="review-issues">
          <div class="review-panel__header review-issues__header">
            <div>
              <div class="review-panel__title">
                质控问题
              </div>
              <div class="review-panel__desc">
                共 {{ displayedIssueCount }} 项，点击问题可联动定位左侧原文。
              </div>
            </div>
            <a-button
              size="small"
              type="text"
              class="review-issues__reload"
              @click="loadDefects"
            >
              <ReloadOutlined :spin="defectLoading" />
            </a-button>
          </div>

          <a-spin
            :spinning="defectLoading"
            class="review-issues__body"
          >
            <div
              v-if="displayedIssueCount === 0"
              class="review-empty review-empty--issues"
            >
              <div class="review-empty__title">
                暂无质控问题
              </div>
              <div class="review-empty__desc">
                当前病历没有待联审的质控项
              </div>
            </div>

            <div
              v-else-if="defectList.length > 0"
              class="review-issue-list"
            >
              <div
                v-for="defect in defectList"
                :key="defect.id"
                class="review-issue-card"
                :class="{ 'review-issue-card--active': selectedDefectId === defect.id }"
                @click="handleDefectSelect(defect)"
              >
                <div class="review-issue-card__top">
                  <div class="review-issue-card__title-wrap">
                    <span
                      class="review-issue-card__dot"
                      :class="{
                        'review-issue-card__dot--critical':
                          defect.severity === 'critical' || defect.severity === 'error',
                        'review-issue-card__dot--warning': defect.severity === 'warning',
                        'review-issue-card__dot--info': defect.severity === 'info',
                      }"
                    />
                    <span class="review-issue-card__title">{{ defect.rule_name }}</span>
                  </div>
                  <span
                    class="review-issue-card__status"
                    :class="{
                      'review-issue-card__status--pending': defect.status === 'pending',
                      'review-issue-card__status--urged': defect.status === 'urged',
                      'review-issue-card__status--approved': defect.status === 'approved',
                      'review-issue-card__status--rejected': defect.status === 'rejected',
                      'review-issue-card__status--remediated': defect.status === 'remediated',
                    }"
                  >
                    {{ getDefectStatusText(defect.status) }}
                  </span>
                </div>
                <div class="review-issue-card__summary line-clamp-2">
                  {{ defect.description }}
                </div>
                <div class="review-issue-card__meta">
                  <span>分类：{{ defect.category }}</span>
                  <span>位置：{{ defect.location }}</span>
                </div>
                <QCReviewActionBar
                  v-if="selectedDefectId === defect.id"
                  :defect="defect"
                  class="review-issue-card__actions"
                  @action-done="handleActionDone"
                />
              </div>
            </div>

            <div
              v-else
              class="review-issue-list"
            >
              <div
                v-for="issue in reviewItemList"
                :key="issue.id"
                class="review-issue-card"
                :class="{ 'review-issue-card--active': selectedReviewIssueId === issue.id }"
                @click="handleReviewIssueSelect(issue)"
              >
                <div class="review-issue-card__top review-issue-card__top--start">
                  <div class="review-issue-card__title-block">
                    <div class="review-issue-card__title">
                      {{ issue.rule_code ? `${issue.rule_code} · ` : ''
                      }}{{ issue.rule_name || '质控规则' }}
                    </div>
                    <div class="review-issue-card__chips">
                      <span
                        class="review-issue-card__pill"
                        :class="getReviewStatusClass(issue.status)"
                      >
                        {{ getReviewStatusText(issue.status) }}
                      </span>
                      <span
                        v-if="issue.document_type"
                        class="review-issue-card__pill review-issue-card__pill--plain"
                      >
                        {{ issue.document_type }}
                      </span>
                      <span
                        v-if="issue.rule_family"
                        class="review-issue-card__pill review-issue-card__pill--plain"
                      >
                        {{ issue.rule_family }}
                      </span>
                      <span
                        v-if="issue.defect_level"
                        class="review-issue-card__pill review-issue-card__pill--plain"
                      >
                        {{ issue.defect_level }}
                      </span>
                    </div>
                  </div>
                  <span
                    v-if="issue.confidence !== null && issue.confidence !== undefined"
                    class="review-issue-card__confidence"
                  >
                    {{ Number(issue.confidence).toFixed(2) }}
                  </span>
                </div>
                <div
                  v-if="issue.findings"
                  class="review-issue-card__section"
                >
                  <span class="review-issue-card__section-label">结论</span>
                  <span>{{ issue.findings }}</span>
                </div>
                <div
                  v-if="issue.evidence"
                  class="review-issue-card__section"
                >
                  <span class="review-issue-card__section-label">证据</span>
                  <span>{{ issue.evidence }}</span>
                </div>
                <div
                  v-if="issue.suggestion"
                  class="review-issue-card__section review-issue-card__section--suggestion"
                >
                  <span class="review-issue-card__section-label">建议</span>
                  <span>{{ issue.suggestion }}</span>
                </div>
              </div>
            </div>
          </a-spin>
        </aside>
      </section>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ReloadOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getDefectList, getRecordDetail, type DefectItem } from '@/api/qcAdmin'
import QCReviewActionBar from './QCReviewActionBar.vue'

interface RecordData {
  id: string
  record_id: string
  patient_name?: string
  department?: string
  discharge_date?: string
  score?: number
  defect_count?: number
  status?: string
}

interface ReviewIssueItem {
  id: string
  source?: string
  job_id?: string
  record_id: string
  visit_id?: string
  patient_name?: string
  rule_code?: string
  rule_name: string
  status: 'non_compliant' | 'uncertain' | 'compliant' | 'not_applicable'
  document_type?: string
  rule_family?: string
  defect_level?: string
  findings?: string
  evidence?: string
  suggestion?: string
  confidence?: number | null
}

interface ReviewDocItem {
  id: string
  doc_key: string
  doc_type: string
  doc_name: string
  content: string
  has_content: boolean
  length: number
  document_id?: string
  document_title?: string
  sort_time?: string
  record_time?: string
  source_table?: string
  group_key?: string
  source_fields?: Array<{
    source_field?: string
    raw_value_preview?: string
    used?: boolean
  }>
  sections?: Array<{
    section_key?: string
    section_label?: string
    text?: string
    source_field?: string
  }>
  assembly_status?: string
  data_quality_flags?: string[]
  order_filter?: OrderFilter
}

interface ReviewDocTreeNode {
  id: string
  doc_key: string
  doc_type: string
  title: string
  record_time?: string
  has_content: boolean
  length: number
}

interface ReviewDocTreeGroup {
  key: string
  label: string
  count: number
  children: ReviewDocTreeNode[]
}

interface DocParagraphBlock {
  key: string
  text: string
}

interface DocSectionBlock {
  key: string
  title: string
  sourceField?: string
  blocks: DocParagraphBlock[]
}

interface HighlightTarget {
  docKey: string
  blockKey: string
  snippet: string
  docTitle: string
}

type OrderFilter = 'all' | 'long' | 'temp' | 'drug' | 'nondrug'

interface OrderRow {
  key: string
  sourceDocKey: string
  blockKey: string
  orderType: 'long' | 'temp' | 'unknown'
  orderTypeLabel: string
  category: 'drug' | 'nondrug' | 'unknown'
  categoryLabel: string
  content: string
  time: string
  startTime: string
  stopTime: string
  status: string
  doctor: string
  doseUsage: string
  searchText: string
}

type SelectableIssue = {
  id: string
  rule_name?: string
  document_type?: string
  evidence?: string
  findings?: string
  suggestion?: string
}

const DOC_GROUP_LABELS: Record<string, string> = {
  all: '全部',
  frontpage: '病案首页(临床医生)',
  admission: '入院记录',
  course: '病程记录',
  exam_attention: '检查检验摘要',
  lab_results: '检验报告',
  exam_results: '检查报告',
  surgery: '手术相关记录',
  consult_discussion: '查房/会诊/讨论',
  terminal: '出院记录',
  orders: '医嘱',
  index_coding_settlement: '首页结算',
}

const DOC_TYPE_LABELS: Record<string, string> = {
  mr: '病案首页',
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  consultation_record: '会诊记录',
  rescue_record: '抢救记录',
  exam_attention_report: '检查关注摘要',
  lab_attention_report: '检验关注摘要',
  exam_master: '检查结果',
  exam_item_report: '检查结果',
  labtest_master: '检验申请单',
  labtest_item_report: '检验明细',
  surgery_record: '手术记录',
  anesthesia_record: '麻醉记录',
  presurg_summary: '术前小结',
  presurg_discussion: '术前讨论',
  surgery_safecheck_record: '手术安全核查记录',
  postsurg_firstcourse_record: '术后首次病程记录',
  discharge_record: '出院记录',
  death_record: '死亡记录',
  inpat_drug_order: '药品医嘱',
  inpat_nondrug_order: '非药品医嘱',
}

const STRUCTURED_FIELD_ONLY_DOC_TYPES = new Set([
  'surgery_record',
  'anesthesia_record',
  'presurg_summary',
  'presurg_discussion',
  'surgery_safecheck_record',
  'postsurg_firstcourse_record',
])

const props = defineProps<{
  visible: boolean
  record: RecordData | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
  (e: 'refresh'): void
}>()

const defectLoading = ref(false)
const defectList = ref<DefectItem[]>([])
const reviewItemList = ref<ReviewIssueItem[]>([])
const selectedDefectId = ref<string | null>(null)
const selectedReviewIssueId = ref<string | null>(null)
const docLoading = ref(false)
const recordDetail = ref<Record<string, unknown> | null>(null)
const activeDocGroup = ref('all')
const activeCourseSubtype = ref('all')
const activeDocKey = ref('')
const orderOverviewFilter = ref<OrderFilter>('all')
const orderKeyword = ref('')
const sidebarDocFilter = ref('all')
const expandedSidebarGroups = ref<string[]>(['course'])
const activeHighlightTarget = ref<HighlightTarget | null>(null)
const highlightBlockElements = new Map<string, HTMLElement>()

const ORDER_OVERVIEW_DOC_PREFIX = '__orders_overview__'

const ORDER_FILTER_LABELS: Record<OrderFilter, string> = {
  all: '全部',
  long: '长期',
  temp: '临时',
  drug: '药品',
  nondrug: '非药品',
}

const FIELD_LABELS: Record<string, string> = {
  record_time: '记录时间',
  department: '科室',
  dept_name: '科室',
  ward_name: '病房',
  ward_no: '病房',
  doctor_name: '医生',
  recorder_name: '记录者',
  submitter: '记录者',
  ward_round_doctor_name: '查房医生',
  ward_round_type: '查房类型',
  participant_names: '参加人员',
  consultation_department: '会诊科室',
  consultation_doctor_name: '会诊医师',
  consultation_reason: '会诊理由',
  consultation_opinion: '会诊意见',
  chief_complaint: '主诉',
  history_of_present_illness: '现病史',
  present_illness_history: '现病史',
  past_history: '既往史',
  personal_history: '个人史',
  marital_delivery_history: '婚育史',
  menstrual_history: '月经史',
  marital_history: '婚育史',
  family_history: '家族史',
  diagnosis: '诊断',
  admission_condition: '入院情况',
  treatment_course: '诊疗经过',
  discharge_order: '出院医嘱',
  discharge_condition: '出院情况',
  discharge_diagnosis: '出院诊断',
  discharge_advice: '出院建议',
  allergy_history: '过敏史',
  drug_allergy_history: '药物过敏史',
  food_allergy_history: '食物过敏史',
  physical_examination: '体格检查',
  checkup: '体格检查',
  checkup_special: '专科情况',
  assist_exam: '辅助检查',
  specialist_examination: '专科检查',
  auxiliary_examination: '辅助检查',
  admission_diagnosis: '入院诊断',
  discharge_medication: '出院带药',
  surgeon_sign: '手术医生签名',
  presurg_summary: '术前小结',
  surgery_name: '手术项目',
  surgery_code: '手术编码',
  surgery_level: '手术等级',
  surgical_level: '手术等级',
  surgeon: '手术医师',
  first_assistant: '手术I助',
  second_assistant: '手术II助',
  anesthesiologist: '麻醉医师',
  anesthesia_method: '麻醉方式',
  preoperative_diagnosis: '术前诊断',
  intraoperative_diagnosis: '术中诊断',
  postoperative_diagnosis: '术后诊断',
  surgery_process: '手术经过',
  surgical_incisionheal_level: '切口愈合等级',
  surgery_begin_time: '手术开始时间',
  surgery_end_time: '手术结束时间',
  blood_loss: '失血量',
  other_content: '其他内容',
  record_content: '记录内容',
  order_name: '医嘱内容',
  order_text: '医嘱内容',
  order_content: '医嘱内容',
  order_type: '医嘱类型',
  order_class: '医嘱类别',
  order_status: '医嘱状态',
  prescribed_datetime: '开立时间',
  start_time: '开始时间',
  stop_time: '停止时间',
  dosage: '剂量',
  frequency: '频次',
  usage: '用法',
  route: '途径',
  prescriber: '开立医生',
  doctor: '医生',
}

const EN_FIELD_LABELS: Record<string, string> = {
  'admission condition': '入院情况',
  'treatment course': '诊疗经过',
  'discharge order': '出院医嘱',
  'discharge condition': '出院情况',
  'discharge diagnosis': '出院诊断',
  'discharge advice': '出院建议',
  'chief complaint': '主诉',
  checkup: '体格检查',
  'assist exam': '辅助检查',
  'checkup special': '专科情况',
  'history of present illness': '现病史',
  'present illness history': '现病史',
  'past history': '既往史',
  'personal history': '个人史',
  'menstrual history': '月经史',
  'marital history': '婚育史',
  'family history': '家族史',
  'allergy history': '过敏史',
  'drug allergy history': '药物过敏史',
  'food allergy history': '食物过敏史',
  'physical examination': '体格检查',
  'specialist examination': '专科检查',
  'auxiliary examination': '辅助检查',
  'admission diagnosis': '入院诊断',
  'discharge medication': '出院带药',
}

const COURSE_SUBTYPE_LABELS: Record<string, string> = {
  all: '全部',
  first_course: '首次病程',
  senior_round: '查房记录',
  daily_course: '日常病程',
  consultation: '会诊记录',
  rescue: '抢救记录',
  postoperative: '术后病程',
  other: '其他',
}

function safeText(value: unknown): string {
  return String(value || '').trim()
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function normalizeSearchText(value: string): string {
  return safeText(value)
    .replace(/【[^】]*】/g, '')
    .replace(/\[[^\]]*]/g, '')
    .replace(/\s+/g, '')
    .replace(/[：:，,。；;、]/g, '')
}

function splitReadableParagraphs(text: string): string[] {
  const normalized = safeText(text).replace(/\r/g, '')
  if (!normalized) return []
  const lineBlocks = normalized
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (lineBlocks.length > 1) return lineBlocks

  const sentences = normalized
    .split(/(?<=[。！？；;])/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (sentences.length <= 1) return [normalized]

  const blocks: string[] = []
  let current = ''
  let sentenceCount = 0
  for (const sentence of sentences) {
    const next = current ? `${current}${sentence}` : sentence
    if (current && (next.length > 110 || sentenceCount >= 2)) {
      blocks.push(current)
      current = sentence
      sentenceCount = 1
    } else {
      current = next
      sentenceCount += 1
    }
  }
  if (current) blocks.push(current)
  return blocks
}

function extractIssueSearchText(
  issue: Pick<SelectableIssue, 'evidence' | 'findings' | 'rule_name'>,
): string {
  const evidence = safeText(issue.evidence)
  if (evidence) return evidence
  const findings = safeText(issue.findings)
  if (findings) return findings
  return safeText(issue.rule_name)
}

function matchesDocType(doc: ReviewDocItem, documentType?: string): boolean {
  const query = safeText(documentType).toLowerCase()
  if (!query) return false
  if ((query.includes('order') || query.includes('医嘱')) && isOrderDoc(doc)) return true
  const candidates = [
    safeText(doc.doc_type).toLowerCase(),
    safeText(doc.source_table).toLowerCase(),
    safeText(doc.document_title).toLowerCase(),
    safeText(doc.doc_name).toLowerCase(),
  ]
  return candidates.some((item) => item && (item.includes(query) || query.includes(item)))
}

function isOrderIssue(issue: SelectableIssue): boolean {
  const probe = [
    issue.document_type,
    issue.evidence,
    issue.findings,
    issue.suggestion,
    issue.rule_name,
  ]
    .map((item) => safeText(item).toLowerCase())
    .join(' ')
  return (
    probe.includes('order') ||
    probe.includes('医嘱') ||
    probe.includes('长期') ||
    probe.includes('临时')
  )
}

function formatDocTime(value?: string): string {
  const raw = safeText(value)
  if (!raw) return ''
  const normalized = raw.endsWith('Z') ? raw : raw.replace(' ', 'T')
  const date = new Date(normalized)
  if (!Number.isNaN(date.getTime())) {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
    const parts = formatter.formatToParts(date)
    const get = (type: Intl.DateTimeFormatPartTypes) =>
      parts.find((part) => part.type === type)?.value || ''
    return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
  }
  return raw
}

function formatOrderDate(value?: string): string {
  const formatted = formatDocTime(value)
  return formatted ? formatted.slice(0, 16) : ''
}

function isOrderDoc(
  doc?: Pick<
    ReviewDocItem,
    'doc_type' | 'source_table' | 'group_key' | 'document_title' | 'doc_name'
  > | null,
): boolean {
  if (!doc) return false
  if (safeText(doc.group_key) === 'orders') return true
  const probe = [doc.doc_type, doc.source_table, doc.document_title, doc.doc_name]
    .map((item) => safeText(item).toLowerCase())
    .join(' ')
  return probe.includes('order') || probe.includes('医嘱')
}

function buildSourceFieldMap(doc: ReviewDocItem): Map<string, string> {
  const fields = new Map<string, string>()
  for (const field of doc.source_fields || []) {
    const key = safeText(field?.source_field).toLowerCase()
    const value = safeText(field?.raw_value_preview)
    if (key && value) fields.set(key, value)
  }
  return fields
}

function pickFieldValue(fields: Map<string, string>, keys: string[]): string {
  for (const key of keys) {
    const value = fields.get(key.toLowerCase())
    if (value) return value
  }
  return ''
}

function inferOrderTypeFromText(text: string): OrderRow['orderType'] {
  if (/临时医嘱|临嘱|临时/u.test(text)) return 'temp'
  if (/长期医嘱|长嘱|长期/u.test(text)) return 'long'
  return 'unknown'
}

function inferOrderCategoryFromText(text: string): OrderRow['category'] {
  const lower = text.toLowerCase()
  if (lower.includes('drug_order') || /药品|用药|片|针|注射|胶囊|颗粒/u.test(text)) {
    return 'drug'
  }
  if (
    lower.includes('nondrug_order') ||
    /非药品|治疗|检查|检验|护理|康复|理疗|会诊|手术|处置/u.test(text)
  ) {
    return 'nondrug'
  }
  return 'unknown'
}

function formatOrderTypeLabel(type: OrderRow['orderType']): string {
  if (type === 'long') return '长期'
  if (type === 'temp') return '临时'
  return '未标记'
}

function formatOrderCategoryLabel(category: OrderRow['category']): string {
  if (category === 'drug') return '药品'
  if (category === 'nondrug') return '非药品'
  return '未标记'
}

function normalizeOrderRow(doc: ReviewDocItem, index: number): OrderRow {
  const fields = buildSourceFieldMap(doc)
  const title = safeText(doc.document_title || doc.doc_name)
  const content =
    pickFieldValue(fields, [
      'order_name',
      'order_text',
      'order_content',
      'order_item_name',
      'item_name',
      'name',
      'prescription_name',
    ]) ||
    title ||
    safeText(doc.content) ||
    '未命名医嘱'
  const typeProbe = [
    pickFieldValue(fields, ['order_type', 'order_class', 'type', 'class']),
    doc.doc_type,
    doc.source_table,
    title,
    doc.content,
  ].join(' ')
  const categoryProbe = [doc.source_table, doc.doc_type, title, content, doc.content].join(' ')
  const orderType = inferOrderTypeFromText(typeProbe)
  const category = inferOrderCategoryFromText(categoryProbe)
  const startTime = formatOrderDate(
    pickFieldValue(fields, [
      'start_time',
      'start_datetime',
      'prescribed_datetime',
      'order_time',
      'record_time',
      'create_time',
    ]) ||
      doc.record_time ||
      doc.sort_time,
  )
  const stopTime = formatOrderDate(
    pickFieldValue(fields, ['stop_time', 'stop_datetime', 'end_time', 'end_datetime']),
  )
  const doseUsage = [
    pickFieldValue(fields, ['dosage', 'dose', 'single_dose']),
    pickFieldValue(fields, ['frequency', 'freq']),
    pickFieldValue(fields, ['usage', 'route', 'administration_route']),
  ]
    .filter(Boolean)
    .join(' / ')
  const status = pickFieldValue(fields, ['order_status', 'status', 'execute_status'])
  const doctor = pickFieldValue(fields, [
    'doctor',
    'doctor_name',
    'prescriber',
    'prescribed_by',
    'submitter',
    'last_modifier',
  ])
  const searchText = [
    content,
    typeProbe,
    categoryProbe,
    startTime,
    stopTime,
    doseUsage,
    status,
    doctor,
  ].join(' ')
  const key = `${doc.doc_key}::order-${index}`
  return {
    key,
    sourceDocKey: doc.doc_key,
    blockKey: `order-row-${index}`,
    orderType,
    orderTypeLabel: formatOrderTypeLabel(orderType),
    category,
    categoryLabel: formatOrderCategoryLabel(category),
    content,
    time: startTime,
    startTime,
    stopTime,
    status,
    doctor,
    doseUsage,
    searchText,
  }
}

function normalizeReviewDocItem(raw: unknown, index: number): ReviewDocItem | null {
  const source = (raw || {}) as Record<string, unknown>
  const id =
    safeText(source.document_id) ||
    safeText(source.id) ||
    safeText(source.doc_id) ||
    `${safeText(source.doc_type || source.type || source.source_table) || 'doc'}-${index}`
  const docType =
    safeText(source.doc_type) ||
    safeText(source.type) ||
    safeText(source.document_type) ||
    safeText(source.source_table)
  const content = safeText(source.content)
  const hasContent =
    typeof source.has_content === 'boolean'
      ? source.has_content
      : Boolean(content || Number(source.length || 0) > 0)
  const title =
    safeText(source.document_title) ||
    safeText(source.doc_name) ||
    safeText(source.label) ||
    DOC_TYPE_LABELS[docType] ||
    docType ||
    '未命名文书'
  return {
    id,
    doc_key: safeText(source.doc_key) || `${docType || 'unknown'}::${id}`,
    doc_type: docType,
    doc_name: title,
    content,
    has_content: hasContent,
    length: Number(source.length || content.length || 0),
    document_id: safeText(source.document_id) || id,
    document_title: safeText(source.document_title) || title,
    sort_time: safeText(source.sort_time) || safeText(source.record_time) || undefined,
    record_time: safeText(source.record_time) || safeText(source.sort_time) || undefined,
    source_table: safeText(source.source_table) || docType || undefined,
    group_key: safeText(source.group_key) || undefined,
    source_fields: Array.isArray(source.source_fields)
      ? source.source_fields
          .filter((item) => item && typeof item === 'object')
          .map((item) => item as ReviewDocItem['source_fields'][number])
      : [],
    sections: Array.isArray(source.sections)
      ? source.sections
          .filter((item) => item && typeof item === 'object')
          .map((item) => item as ReviewDocItem['sections'][number])
      : [],
    assembly_status: safeText(source.assembly_status) || undefined,
    data_quality_flags: Array.isArray(source.data_quality_flags)
      ? source.data_quality_flags.map((item) => safeText(item)).filter(Boolean)
      : [],
  }
}

function inferDocGroupKey(doc: ReviewDocItem): string {
  const explicit = safeText(doc.group_key)
  if (explicit) return explicit
  const docType = safeText(doc.doc_type || doc.source_table).toLowerCase()
  if (['mr', 'diagnosis', 'mr_surgery', 'mr_cost'].includes(docType)) return 'frontpage'
  if (docType.includes('admission')) return 'admission'
  if (docType.includes('attention_report')) return 'exam_attention'
  if (docType.includes('labtest')) return 'lab_results'
  if (docType.includes('exam')) return 'exam_results'
  if (docType.includes('consult') || docType.includes('discussion')) return 'consult_discussion'
  if (docType.includes('course') || docType.includes('rescue') || docType.includes('handoff')) {
    return 'course'
  }
  if (
    docType.includes('surgery') ||
    docType.includes('anesthesia') ||
    docType.includes('presurg')
  ) {
    return 'surgery'
  }
  if (docType.includes('discharge') || docType.includes('death')) return 'terminal'
  if (docType.includes('order')) return 'orders'
  return 'course'
}

function prettifyFieldLabel(fieldName?: string): string {
  const raw = safeText(fieldName)
  if (!raw) return '字段'
  if (FIELD_LABELS[raw]) return FIELD_LABELS[raw]
  const normalized = raw.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase()
  if (FIELD_LABELS[normalized]) return FIELD_LABELS[normalized]
  if (EN_FIELD_LABELS[normalized]) return EN_FIELD_LABELS[normalized]
  return raw
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .replace(/\s+/g, ' ')
}

function buildDocFieldList(doc?: ReviewDocItem | null) {
  const fields = doc?.source_fields || []
  return fields
    .filter((field) => field?.used !== false)
    .map((field, index) => ({
      key: safeText(field?.source_field) || `field-${index}`,
      blockKey: `field-block-${safeText(field?.source_field) || index}`,
      label: prettifyFieldLabel(field?.source_field),
      value: safeText(field?.raw_value_preview),
    }))
}

function shouldSuppressPlainContentFallback(doc?: ReviewDocItem | null): boolean {
  if (!doc) return false
  const docType = safeText(doc.doc_type || doc.source_table).toLowerCase()
  return (
    STRUCTURED_FIELD_ONLY_DOC_TYPES.has(docType) &&
    buildDocFieldList(doc).length > 0 &&
    (doc.sections || []).length === 0
  )
}

function buildCourseTitleProbeText(doc: ReviewDocItem): string {
  return [
    safeText(doc.document_title),
    safeText(doc.doc_name),
    safeText(doc.content),
    ...(doc.sections || []).map((section) => safeText(section?.text)),
  ]
    .filter(Boolean)
    .join('\n')
}

function inferCourseDisplayTitle(doc: ReviewDocItem): string {
  const docType = safeText(doc.doc_type || doc.source_table).toLowerCase()
  const originalTitle = safeText(doc.document_title || doc.doc_name)
  const probeText = buildCourseTitleProbeText(doc)

  if (docType.includes('first_course')) return originalTitle || '首次病程记录'
  if (docType.includes('consult')) return originalTitle || '会诊记录'
  if (docType.includes('rescue')) return originalTitle || '抢救记录'
  if (docType.includes('postsurg')) return originalTitle || '术后病程记录'

  if (docType.includes('senior_course')) {
    if (originalTitle) return originalTitle
    if (/主任医师.*查房|副主任医师.*查房|主治医师.*查房/u.test(probeText)) {
      const matched = probeText.match(
        /[^。；\n]{0,24}(?:主任医师|副主任医师|主治医师)[^。；\n]{0,12}查房记录?/u,
      )
      return matched?.[0]?.trim() || '上级医师查房记录'
    }
    if (/查房/u.test(probeText)) return '查房记录'
    return '上级医师查房记录'
  }

  if (docType.includes('daily_course')) {
    if (originalTitle && originalTitle !== '日常病程记录') return originalTitle
    if (/转入/u.test(probeText)) return '转入记录'
    if (/转出/u.test(probeText)) return '转出记录'
    if (/今日查房/u.test(probeText)) return '今日查房'
    if (/查房内容|查房记录|查房/u.test(probeText)) return '查房记录'
    return originalTitle || '日常病程记录'
  }

  return originalTitle || DOC_TYPE_LABELS[safeText(doc.doc_type)] || '病历文书'
}

function inferCourseSubtype(doc: ReviewDocItem): string {
  const docType = safeText(doc.doc_type || doc.source_table).toLowerCase()
  if (docType.includes('first_course')) return 'first_course'
  if (docType.includes('senior_course')) return 'senior_round'
  if (docType.includes('daily_course')) {
    return 'daily_course'
  }
  if (docType.includes('consult')) return 'consultation'
  if (docType.includes('rescue')) return 'rescue'
  if (docType.includes('postsurg')) return 'postoperative'
  return 'other'
}

function parseSortTimestamp(value?: string): number {
  const raw = safeText(value)
  if (!raw) return 0
  const normalized = raw.endsWith('Z') ? raw : raw.replace(' ', 'T')
  const timestamp = new Date(normalized).getTime()
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function sortDocsByTimeDesc(docs: ReviewDocItem[]): ReviewDocItem[] {
  return [...docs].sort((left, right) => {
    const timeGap =
      parseSortTimestamp(right.record_time || right.sort_time) -
      parseSortTimestamp(left.record_time || left.sort_time)
    if (timeGap !== 0) return timeGap
    return safeText(right.document_title).localeCompare(safeText(left.document_title), 'zh-CN')
  })
}

function buildTreeNodeFromDoc(doc: ReviewDocItem): ReviewDocTreeNode {
  return {
    id: doc.document_id || doc.id,
    doc_key: doc.doc_key,
    doc_type: doc.doc_type,
    title: doc.document_title || doc.doc_name,
    record_time: doc.record_time || doc.sort_time,
    has_content: doc.has_content,
    length: doc.length,
  }
}

function buildFallbackDocTree(docs: ReviewDocItem[]): ReviewDocTreeGroup[] {
  const groups: Array<{ key: string; label: string }> = [
    { key: 'all', label: '全部' },
    { key: 'frontpage', label: DOC_GROUP_LABELS.frontpage },
    { key: 'admission', label: DOC_GROUP_LABELS.admission },
    { key: 'course', label: DOC_GROUP_LABELS.course },
    { key: 'exam_attention', label: DOC_GROUP_LABELS.exam_attention },
    { key: 'lab_results', label: DOC_GROUP_LABELS.lab_results },
    { key: 'exam_results', label: DOC_GROUP_LABELS.exam_results },
    { key: 'surgery', label: DOC_GROUP_LABELS.surgery },
    { key: 'consult_discussion', label: DOC_GROUP_LABELS.consult_discussion },
    { key: 'terminal', label: DOC_GROUP_LABELS.terminal },
    { key: 'orders', label: DOC_GROUP_LABELS.orders },
  ]
  const byGroup = new Map<string, ReviewDocTreeNode[]>()
  for (const doc of docs) {
    const node = buildTreeNodeFromDoc(doc)
    const groupKey = inferDocGroupKey(doc)
    byGroup.set(groupKey, [...(byGroup.get(groupKey) || []), node])
    byGroup.set('all', [...(byGroup.get('all') || []), node])
  }
  return groups.map((group) => ({
    key: group.key,
    label: group.label,
    count: (byGroup.get(group.key) || []).length,
    children: byGroup.get(group.key) || [],
  }))
}

function normalizeDocTree(rawTree: unknown, docs: ReviewDocItem[]): ReviewDocTreeGroup[] {
  const groups = Array.isArray(rawTree) ? rawTree : []
  const normalized = groups
    .map((rawGroup) => {
      const source = (rawGroup || {}) as Record<string, unknown>
      const groupKey = safeText(source.key || source.group_key)
      const groupLabel =
        safeText(source.label || source.title || source.name) ||
        DOC_GROUP_LABELS[groupKey] ||
        groupKey
      const rawChildren = Array.isArray(source.children)
        ? source.children
        : Array.isArray(source.nodes)
          ? source.nodes
          : []
      const children = rawChildren
        .map((rawNode) => {
          const nodeSource = (rawNode || {}) as Record<string, unknown>
          const id = safeText(nodeSource.id || nodeSource.doc_id || nodeSource.document_id)
          const docType = safeText(nodeSource.doc_type || nodeSource.type)
          const docKey = safeText(nodeSource.doc_key) || (docType && id ? `${docType}::${id}` : '')
          const matched =
            docs.find((doc) => doc.doc_key === docKey) ||
            docs.find((doc) => doc.document_id === id && doc.doc_type === docType)
          return {
            id: id || docKey || matched?.id || '',
            doc_key: docKey || matched?.doc_key || '',
            doc_type: docType || matched?.doc_type || '',
            title:
              safeText(nodeSource.title || nodeSource.label || nodeSource.doc_name) ||
              matched?.doc_name ||
              DOC_TYPE_LABELS[docType] ||
              '未命名文书',
            record_time:
              safeText(nodeSource.record_time || nodeSource.sort_time) ||
              matched?.record_time ||
              matched?.sort_time,
            has_content:
              typeof nodeSource.has_content === 'boolean'
                ? nodeSource.has_content
                : Boolean(matched?.has_content),
            length: Number(nodeSource.length || matched?.length || 0),
          } as ReviewDocTreeNode
        })
        .filter((node) => Boolean(node.id))

      return {
        key: groupKey || groupLabel,
        label: groupLabel,
        count: children.length,
        children,
      } as ReviewDocTreeGroup
    })
    .filter((group) => Boolean(group.key))

  const hasUsefulGroup = normalized.some(
    (group) => group.key !== 'all' && Array.isArray(group.children) && group.children.length > 0,
  )
  if (hasUsefulGroup) return normalized
  if (docs.length > 0) return buildFallbackDocTree(docs)
  return normalized
}

const rawDocumentList = computed(() => {
  const detail = recordDetail.value
  if (!detail) return []
  const documents = (detail.documents as Record<string, unknown> | undefined) || {}
  const rawDocuments = documents.raw_documents
  if (Array.isArray(rawDocuments) && rawDocuments.length > 0) {
    return rawDocuments
  }
  const fallbackDocs = [
    {
      doc_type: 'admission_record',
      document_title: '入院记录',
      content: detail.admissionNote || documents.admissionNote,
    },
    {
      doc_type: 'discharge_record',
      document_title: '出院记录',
      content: detail.dischargeNote || documents.dischargeNote,
    },
    {
      doc_type: 'course_record',
      document_title: '病程记录',
      content: detail.progressNote || documents.progressNote,
      group_key: 'course',
    },
    {
      doc_type: 'surgery_record',
      document_title: '手术相关文书',
      content: detail.surgeryNote || documents.surgeryNote,
      group_key: 'surgery',
    },
  ]
  return fallbackDocs.filter((item) => safeText(item.content))
})

const documentList = computed<ReviewDocItem[]>(() =>
  rawDocumentList.value
    .map((item, index) => normalizeReviewDocItem(item, index))
    .filter((item): item is ReviewDocItem => Boolean(item)),
)

const orderSourceDocs = computed(() => documentList.value.filter((doc) => isOrderDoc(doc)))

const orderRows = computed<OrderRow[]>(() =>
  orderSourceDocs.value
    .map((doc, index) => normalizeOrderRow(doc, index))
    .sort((left, right) => {
      const timeGap = parseSortTimestamp(right.time) - parseSortTimestamp(left.time)
      if (timeGap !== 0) return timeGap
      return safeText(left.content).localeCompare(safeText(right.content), 'zh-CN')
    }),
)

const orderOverviewStats = computed(() => {
  const rows = orderRows.value
  return {
    total: rows.length,
    long: rows.filter((row) => row.orderType === 'long').length,
    temp: rows.filter((row) => row.orderType === 'temp').length,
    drug: rows.filter((row) => row.category === 'drug').length,
    nondrug: rows.filter((row) => row.category === 'nondrug').length,
  }
})

const orderOverviewTimeRange = computed(() => {
  const times = orderRows.value
    .map((row) => row.time || row.startTime)
    .filter(Boolean)
    .sort()
  if (times.length === 0) return ''
  const first = times[0].slice(0, 10)
  const last = times[times.length - 1].slice(0, 10)
  return first === last ? first : `${first} 至 ${last}`
})

function buildOrderOverviewDoc(filter: OrderFilter): ReviewDocItem {
  const stats = orderOverviewStats.value
  const count =
    filter === 'long'
      ? stats.long
      : filter === 'temp'
        ? stats.temp
        : filter === 'drug'
          ? stats.drug
          : filter === 'nondrug'
            ? stats.nondrug
            : stats.total
  const label = filter === 'all' ? '医嘱总览' : `${ORDER_FILTER_LABELS[filter]}医嘱`
  const range = orderOverviewTimeRange.value ? ` · ${orderOverviewTimeRange.value}` : ''
  return {
    id: `${ORDER_OVERVIEW_DOC_PREFIX}${filter}`,
    doc_key: `${ORDER_OVERVIEW_DOC_PREFIX}${filter}`,
    doc_type: 'orders_overview',
    doc_name: `${label} · ${count} 条${range}`,
    content: '',
    has_content: true,
    length: count,
    document_id: `${ORDER_OVERVIEW_DOC_PREFIX}${filter}`,
    document_title: `${label} · ${count} 条${range}`,
    source_table: 'orders_overview',
    group_key: 'orders',
    order_filter: filter,
  }
}

const orderSummaryDocs = computed<ReviewDocItem[]>(() => {
  const stats = orderOverviewStats.value
  if (stats.total === 0) return [buildOrderOverviewDoc('all')]
  const summaries: OrderFilter[] = ['all']
  if (stats.temp > 0) summaries.push('temp')
  if (stats.long > 0) summaries.push('long')
  if (stats.drug > 0) summaries.push('drug')
  if (stats.nondrug > 0) summaries.push('nondrug')
  return summaries.map((filter) => buildOrderOverviewDoc(filter))
})

const documentTree = computed<ReviewDocTreeGroup[]>(() => {
  const detail = recordDetail.value
  if (!detail) return []
  const documents = (detail.documents as Record<string, unknown> | undefined) || {}
  const rawTree = detail.documents_tree || documents.documents_tree
  const normalized = normalizeDocTree(rawTree, documentList.value)
  if (orderSourceDocs.value.length === 0) return normalized
  const orderNodes = orderSourceDocs.value.map((doc) => buildTreeNodeFromDoc(doc))
  const orderGroupIndex = normalized.findIndex((group) => group.key === 'orders')
  if (orderGroupIndex < 0) {
    return [
      ...normalized,
      {
        key: 'orders',
        label: DOC_GROUP_LABELS.orders,
        count: orderNodes.length,
        children: orderNodes,
      },
    ]
  }
  if (normalized[orderGroupIndex].children.length > 0) return normalized
  return normalized.map((group, index) =>
    index === orderGroupIndex
      ? {
          ...group,
          count: orderNodes.length,
          children: orderNodes,
        }
      : group,
  )
})

const displayDocGroups = computed(() =>
  documentTree.value.filter(
    (group) => group.key !== 'all' && Array.isArray(group.children) && group.children.length > 0,
  ),
)

const sidebarFilterOptions = computed(() => [
  { label: '所有单据', value: 'all' },
  ...displayDocGroups.value.map((group) => ({
    label: group.label,
    value: group.key,
  })),
])

const fixedFrontpageDoc = computed<ReviewDocItem | null>(() => {
  const group = displayDocGroups.value.find((item) => item.key === 'frontpage')
  if (!group) return null
  return getSidebarGroupDocs(group)[0] || null
})

const visibleSidebarGroups = computed(() => {
  const groups = displayDocGroups.value.filter((group) => group.key !== 'frontpage')
  if (sidebarDocFilter.value === 'all') return groups
  if (sidebarDocFilter.value === 'frontpage') return []
  return groups.filter((group) => group.key === sidebarDocFilter.value)
})

const currentGroupNodes = computed<ReviewDocTreeNode[]>(() => {
  const groupKey = safeText(activeDocGroup.value)
  if (!groupKey || groupKey === 'all') {
    return documentList.value.map((doc) => buildTreeNodeFromDoc(doc))
  }
  return displayDocGroups.value.find((group) => group.key === groupKey)?.children || []
})

function resolveDocByNode(node: ReviewDocTreeNode): ReviewDocItem | undefined {
  return (
    documentList.value.find((doc) => doc.doc_key === node.doc_key) ||
    documentList.value.find(
      (doc) => doc.document_id === node.id && doc.doc_type === node.doc_type,
    ) ||
    documentList.value.find((doc) => doc.doc_type === node.doc_type)
  )
}

const currentGroupDocs = computed<ReviewDocItem[]>(() =>
  sortDocsByTimeDesc(
    currentGroupNodes.value
      .map((node) => resolveDocByNode(node))
      .filter((doc): doc is ReviewDocItem => Boolean(doc))
      .filter(
        (doc, index, list) => list.findIndex((item) => item.doc_key === doc.doc_key) === index,
      ),
  ),
)

const courseSubtypeOptions = computed(() => {
  if (activeDocGroup.value !== 'course') return []
  const availableTypes = new Set(currentGroupDocs.value.map((doc) => inferCourseSubtype(doc)))
  const options = [{ label: COURSE_SUBTYPE_LABELS.all, value: 'all' }]
  Object.entries(COURSE_SUBTYPE_LABELS)
    .filter(([key]) => key !== 'all' && availableTypes.has(key))
    .forEach(([key, label]) => {
      options.push({ label, value: key })
    })
  return options
})

const visibleCurrentGroupDocs = computed<ReviewDocItem[]>(() => {
  if (activeDocGroup.value !== 'course' || activeCourseSubtype.value === 'all') {
    return currentGroupDocs.value
  }
  return currentGroupDocs.value.filter(
    (doc) => inferCourseSubtype(doc) === activeCourseSubtype.value,
  )
})

const isOrderOverviewActive = computed(
  () =>
    activeDocGroup.value === 'orders' &&
    safeText(activeDocKey.value).startsWith(ORDER_OVERVIEW_DOC_PREFIX),
)

const currentDoc = computed<ReviewDocItem | null>(() => {
  if (isOrderOverviewActive.value) return null
  if (!visibleCurrentGroupDocs.value.length) return null
  return (
    visibleCurrentGroupDocs.value.find((doc) => doc.doc_key === activeDocKey.value) ||
    visibleCurrentGroupDocs.value[0] ||
    null
  )
})

const currentDocContent = computed(() => currentDoc.value?.content || '')
const shouldShowCurrentDocPlainContent = computed(
  () => Boolean(currentDocContent.value) && !shouldSuppressPlainContentFallback(currentDoc.value),
)
const currentDocTitle = computed(
  () => currentDoc.value?.document_title || currentDoc.value?.doc_name || '病历文书',
)
const currentDocTypeLabel = computed(() => {
  const doc = currentDoc.value
  if (!doc) return '病历文书'
  return DOC_TYPE_LABELS[safeText(doc.doc_type)] || doc.doc_name || '病历文书'
})
const currentDocReadableTime = computed(() =>
  formatDocTime(currentDoc.value?.record_time || currentDoc.value?.sort_time),
)
const currentDocMeta = computed(() => {
  if (!currentDoc.value) return ''
  const parts: string[] = []
  if (currentDoc.value.document_id) {
    parts.push(`文书编号：${currentDoc.value.document_id}`)
  }
  if (currentDoc.value.length) parts.push(`正文长度：${currentDoc.value.length}`)
  return parts.filter(Boolean).join(' · ')
})

function mapCurrentDocFlag(flag: string): string | null {
  const raw = safeText(flag)
  if (!raw) return null
  const known: Record<string, string> = {
    partial: '结构待完善',
  }
  if (known[raw]) return known[raw]
  return /[\u4e00-\u9fa5]/.test(raw) ? raw : null
}

const currentDocVisibleFlags = computed(() =>
  (currentDoc.value?.data_quality_flags || [])
    .map((flag) => mapCurrentDocFlag(flag))
    .filter((flag): flag is string => Boolean(flag)),
)

const documentCount = computed(() => documentList.value.length)

const orderOverviewTitle = computed(() => {
  const selected = orderSummaryDocs.value.find((doc) => doc.doc_key === activeDocKey.value)
  return selected?.document_title || '医嘱总览'
})

const orderOverviewMeta = computed(() =>
  orderOverviewStats.value.total > 0
    ? `按时间倒序展示医嘱明细，支持类型筛选和关键词搜索。`
    : '当前病历尚未装配可展示医嘱。',
)

const orderFilterOptions = computed(() =>
  orderSummaryDocs.value.map((doc) => ({
    label: ORDER_FILTER_LABELS[doc.order_filter || 'all'],
    value: doc.order_filter || 'all',
  })),
)

const filteredOrderRows = computed(() => {
  const filter = orderOverviewFilter.value
  const keyword = normalizeSearchText(orderKeyword.value)
  return orderRows.value.filter((row) => {
    const filterMatched =
      filter === 'all' ||
      (filter === 'long' && row.orderType === 'long') ||
      (filter === 'temp' && row.orderType === 'temp') ||
      (filter === 'drug' && row.category === 'drug') ||
      (filter === 'nondrug' && row.category === 'nondrug')
    if (!filterMatched) return false
    if (!keyword) return true
    return normalizeSearchText(row.searchText).includes(keyword)
  })
})

const showOrderDoseUsageColumn = computed(() =>
  filteredOrderRows.value.some((row) => Boolean(row.doseUsage)),
)
const showOrderStopTimeColumn = computed(() =>
  filteredOrderRows.value.some((row) => Boolean(row.stopTime)),
)
const showOrderStatusColumn = computed(() =>
  filteredOrderRows.value.some((row) => Boolean(row.status)),
)
const showOrderDoctorColumn = computed(() =>
  filteredOrderRows.value.some((row) => Boolean(row.doctor)),
)

const currentDocFieldList = computed(() => buildDocFieldList(currentDoc.value))

const currentDocSectionList = computed(() => {
  const sections = currentDoc.value?.sections || []
  return sections
    .map((section, index) => ({
      key: safeText(section?.section_key) || `section-${index}`,
      title: safeText(section?.section_label)
        ? prettifyFieldLabel(section?.section_label)
        : `正文段落 ${index + 1}`,
      text: safeText(section?.text),
      sourceField: safeText(section?.source_field),
    }))
    .filter((section) => Boolean(section.text))
})

const currentDocSectionBlocks = computed<DocSectionBlock[]>(() =>
  currentDocSectionList.value
    .map((section) => ({
      key: section.key,
      title: section.title,
      sourceField: section.sourceField,
      blocks: splitReadableParagraphs(section.text).map((text, index) => ({
        key: `${section.key}-block-${index}`,
        text,
      })),
    }))
    .filter((section) => section.blocks.length > 0),
)

const currentDocPlainBlocks = computed<DocParagraphBlock[]>(() =>
  splitReadableParagraphs(currentDocContent.value).map((text, index) => ({
    key: `plain-block-${index}`,
    text,
  })),
)

const currentDocFieldBlocks = computed<DocParagraphBlock[]>(() =>
  currentDocFieldList.value
    .filter((field) => Boolean(safeText(field.value)))
    .map((field) => ({
      key: field.blockKey,
      text: field.value,
    })),
)

const currentDocAllBlocks = computed<DocParagraphBlock[]>(() => {
  const plainBlocks = shouldShowCurrentDocPlainContent.value ? currentDocPlainBlocks.value : []
  if (currentDocFieldBlocks.value.length > 0) {
    const contentBlocks =
      currentDocSectionBlocks.value.length > 0
        ? currentDocSectionBlocks.value.flatMap((section) => section.blocks)
        : plainBlocks
    return [...currentDocFieldBlocks.value, ...contentBlocks]
  }
  if (currentDocSectionBlocks.value.length > 0) {
    return currentDocSectionBlocks.value.flatMap((section) => section.blocks)
  }
  return plainBlocks
})

const activeHighlightBlockKey = computed(() => activeHighlightTarget.value?.blockKey || '')

const activeReviewIssueSummary = computed(() => {
  const target = activeHighlightTarget.value
  if (!target) return ''
  return `已切换到“${target.docTitle}”，并定位到相关原文段落。`
})

function renderDocListTitle(doc: ReviewDocItem): string {
  if (doc.order_filter) return doc.document_title || doc.doc_name
  if (activeDocGroup.value === 'course') {
    return inferCourseDisplayTitle(doc)
  }
  return doc.document_title || doc.doc_name
}

function isSidebarGroupExpandable(group: ReviewDocTreeGroup): boolean {
  if (group.key === 'orders') return true
  return group.children.length > 1
}

function isSidebarGroupExpanded(groupKey: string): boolean {
  return expandedSidebarGroups.value.includes(groupKey)
}

function ensureSidebarGroupExpanded(groupKey: string) {
  if (!expandedSidebarGroups.value.includes(groupKey)) {
    expandedSidebarGroups.value = [...expandedSidebarGroups.value, groupKey]
  }
}

function toggleSidebarGroup(groupKey: string) {
  if (isSidebarGroupExpanded(groupKey)) {
    expandedSidebarGroups.value = expandedSidebarGroups.value.filter((key) => key !== groupKey)
    return
  }
  ensureSidebarGroupExpanded(groupKey)
}

function getSidebarGroupDocs(group: ReviewDocTreeGroup): ReviewDocItem[] {
  if (group.key === 'orders') return orderSummaryDocs.value
  return sortDocsByTimeDesc(
    group.children
      .map((node) => resolveDocByNode(node))
      .filter((doc): doc is ReviewDocItem => Boolean(doc))
      .filter(
        (doc, index, list) => list.findIndex((item) => item.doc_key === doc.doc_key) === index,
      ),
  )
}

function renderSidebarDocDate(doc: ReviewDocItem): string {
  if (doc.order_filter) return '汇总'
  const time = formatDocTime(doc.record_time || doc.sort_time)
  return time ? time.slice(0, 10) : '未标记时间'
}

function renderSidebarDocTitle(doc: ReviewDocItem): string {
  return renderDocListTitle(doc)
}

function handleSidebarAllClick() {
  sidebarDocFilter.value = 'all'
  activeDocGroup.value = 'all'
  activeCourseSubtype.value = 'all'
  syncActiveDocumentSelection()
}

function handleSidebarFrontpageClick() {
  if (!fixedFrontpageDoc.value) return
  sidebarDocFilter.value = 'frontpage'
  activeDocGroup.value = 'frontpage'
  activeCourseSubtype.value = 'all'
  activeDocKey.value = fixedFrontpageDoc.value.doc_key
}

function handleSidebarLeafGroupClick(group: ReviewDocTreeGroup) {
  activeDocGroup.value = group.key
  activeCourseSubtype.value = 'all'
  const firstDoc = getSidebarGroupDocs(group)[0]
  if (firstDoc) {
    activeDocKey.value = firstDoc.doc_key
    if (firstDoc.order_filter) orderOverviewFilter.value = firstDoc.order_filter
  }
}

function handleSidebarGroupHeaderClick(group: ReviewDocTreeGroup) {
  activeDocGroup.value = group.key
  activeCourseSubtype.value = 'all'
  toggleSidebarGroup(group.key)
  const firstDoc = getSidebarGroupDocs(group)[0]
  if (firstDoc && !getSidebarGroupDocs(group).some((doc) => doc.doc_key === activeDocKey.value)) {
    activeDocKey.value = firstDoc.doc_key
    if (firstDoc.order_filter) orderOverviewFilter.value = firstDoc.order_filter
  }
}

function handleSidebarDocClick(groupKey: string, doc: ReviewDocItem) {
  activeDocGroup.value = groupKey
  activeCourseSubtype.value = 'all'
  ensureSidebarGroupExpanded(groupKey)
  activeDocKey.value = doc.doc_key
  if (doc.order_filter) {
    orderOverviewFilter.value = doc.order_filter
    activeHighlightTarget.value = null
  }
}

function setHighlightBlockRef(blockKey: string, el: Element | null) {
  if (el instanceof HTMLElement) {
    highlightBlockElements.set(blockKey, el)
    return
  }
  highlightBlockElements.delete(blockKey)
}

function findHighlightTargetInDoc(
  doc: ReviewDocItem,
  issue: SelectableIssue,
): HighlightTarget | null {
  const queryText = extractIssueSearchText(issue)
  const normalizedQuery = normalizeSearchText(queryText)
  if (!normalizedQuery) return null

  const blocks =
    currentDoc.value?.doc_key === doc.doc_key
      ? currentDocAllBlocks.value
      : (() => {
          const fieldBlocks = buildDocFieldList(doc)
            .map((field) => ({
              key: field.blockKey,
              text: field.value,
            }))
            .filter((field) => Boolean(safeText(field.text)))
          const sections = (doc.sections || [])
            .map((section, index) => {
              const baseKey = safeText(section?.section_key) || `section-${index}`
              return splitReadableParagraphs(safeText(section?.text)).map((text, blockIndex) => ({
                key: `${baseKey}-block-${blockIndex}`,
                text,
              }))
            })
            .flat()
          if (sections.length > 0) return [...fieldBlocks, ...sections]
          if (shouldSuppressPlainContentFallback(doc)) return fieldBlocks
          const plainBlocks = splitReadableParagraphs(doc.content).map((text, index) => ({
            key: `plain-block-${index}`,
            text,
          }))
          return [...fieldBlocks, ...plainBlocks]
        })()

  const matchedBlock = blocks.find((block) =>
    normalizeSearchText(block.text).includes(normalizedQuery),
  )
  if (!matchedBlock) return null
  return {
    docKey: doc.doc_key,
    blockKey: matchedBlock.key,
    snippet: queryText,
    docTitle: doc.document_title || doc.doc_name || '病历文书',
  }
}

function findOrderHighlightTarget(issue: SelectableIssue): HighlightTarget | null {
  if (!isOrderIssue(issue)) return null
  const queryText = extractIssueSearchText(issue)
  const normalizedQuery = normalizeSearchText(queryText)
  const matchedRow = normalizedQuery
    ? orderRows.value.find((row) => normalizeSearchText(row.searchText).includes(normalizedQuery))
    : null
  return {
    docKey: `${ORDER_OVERVIEW_DOC_PREFIX}all`,
    blockKey: matchedRow?.blockKey || '',
    snippet: queryText,
    docTitle: '医嘱总览',
  }
}

function findBestHighlightTarget(issue: SelectableIssue): HighlightTarget | null {
  const orderTarget = findOrderHighlightTarget(issue)
  if (orderTarget) return orderTarget
  const docsByType = documentList.value.filter((doc) => matchesDocType(doc, issue.document_type))
  for (const doc of docsByType) {
    const target = findHighlightTargetInDoc(doc, issue)
    if (target) return target
  }
  for (const doc of documentList.value) {
    const target = findHighlightTargetInDoc(doc, issue)
    if (target) return target
  }
  return null
}

async function applyHighlightTarget(target: HighlightTarget | null) {
  if (!target) {
    activeHighlightTarget.value = null
    return
  }
  if (target.docKey.startsWith(ORDER_OVERVIEW_DOC_PREFIX)) {
    activeDocGroup.value = 'orders'
    activeCourseSubtype.value = 'all'
    activeDocKey.value = target.docKey
    orderOverviewFilter.value = 'all'
    orderKeyword.value = ''
    activeHighlightTarget.value = target.blockKey ? target : null
    await nextTick()
    if (target.blockKey) {
      const el = highlightBlockElements.get(target.blockKey)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    return
  }
  const doc = documentList.value.find((item) => item.doc_key === target.docKey)
  if (!doc) {
    activeHighlightTarget.value = null
    return
  }
  const nextGroup = inferDocGroupKey(doc)
  activeDocGroup.value = nextGroup
  if (nextGroup === 'course') {
    activeCourseSubtype.value = 'all'
  }
  activeDocKey.value = doc.doc_key
  activeHighlightTarget.value = target
  await nextTick()
  const el = highlightBlockElements.get(target.blockKey)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function renderHighlightedText(text: string, snippet: string): string {
  const safeTextValue = escapeHtml(text)
  const normalizedSnippet = normalizeSearchText(snippet)
  if (!normalizedSnippet) return safeTextValue

  const chars = Array.from(text)
  let rawStart = -1
  let rawEnd = -1
  let normalizedCursor = ''
  for (let index = 0; index < chars.length; index += 1) {
    const normalizedChar = normalizeSearchText(chars[index] || '')
    if (!normalizedChar) continue
    normalizedCursor += normalizedChar
    if (normalizedCursor.endsWith(normalizedSnippet)) {
      rawEnd = index + 1
      let remaining = normalizedSnippet.length
      let start = index
      while (start >= 0 && remaining > 0) {
        const width = normalizeSearchText(chars[start] || '').length
        if (width > 0) remaining -= width
        start -= 1
      }
      rawStart = start + 1
      break
    }
  }
  if (rawStart < 0 || rawEnd <= rawStart) return safeTextValue

  const before = escapeHtml(chars.slice(0, rawStart).join(''))
  const hit = escapeHtml(chars.slice(rawStart, rawEnd).join(''))
  const after = escapeHtml(chars.slice(rawEnd).join(''))
  return `${before}<mark class="doc-content__mark">${hit}</mark>${after}`
}

function renderBlockHtml(block: DocParagraphBlock): string {
  const target = activeHighlightTarget.value
  const html =
    target?.blockKey === block.key
      ? renderHighlightedText(block.text, target.snippet)
      : escapeHtml(block.text)
  return sanitizeHtml(html)
}

async function handleReviewIssueSelect(issue: ReviewIssueItem) {
  selectedReviewIssueId.value = issue.id
  selectedDefectId.value = null
  const target = findBestHighlightTarget(issue)
  await applyHighlightTarget(target)
}

async function handleDefectSelect(defect: DefectItem) {
  selectedDefectId.value = defect.id
  selectedReviewIssueId.value = null
  const target = findBestHighlightTarget({
    id: defect.id,
    rule_name: defect.rule_name,
    document_type: defect.location,
    evidence: defect.description,
    findings: defect.description,
  })
  await applyHighlightTarget(target)
}

function syncActiveDocumentSelection() {
  if (!displayDocGroups.value.length) {
    activeDocGroup.value = 'all'
    sidebarDocFilter.value = 'all'
    activeDocKey.value = visibleCurrentGroupDocs.value[0]?.doc_key || ''
    return
  }
  const validGroupKeys = displayDocGroups.value.map((group) => group.key)
  const supportedSidebarFilters = fixedFrontpageDoc.value
    ? [...validGroupKeys, 'frontpage']
    : validGroupKeys
  if (
    sidebarDocFilter.value !== 'all' &&
    !supportedSidebarFilters.includes(sidebarDocFilter.value)
  ) {
    sidebarDocFilter.value = 'all'
  }
  if (activeDocGroup.value === 'frontpage' && fixedFrontpageDoc.value) {
    activeDocKey.value = fixedFrontpageDoc.value.doc_key
    return
  }
  if (!validGroupKeys.includes(activeDocGroup.value)) {
    activeDocGroup.value = validGroupKeys[0]
  }
  const validCourseSubtypes = courseSubtypeOptions.value.map((option) => option.value)
  if (!validCourseSubtypes.includes(activeCourseSubtype.value)) {
    activeCourseSubtype.value = 'all'
  }
  if (activeDocGroup.value === 'orders') {
    const validOrderDocs = orderSummaryDocs.value
    const validOrderKeys = validOrderDocs.map((doc) => doc.doc_key)
    if (!validOrderKeys.includes(activeDocKey.value)) {
      activeDocKey.value = validOrderDocs[0]?.doc_key || `${ORDER_OVERVIEW_DOC_PREFIX}all`
      orderOverviewFilter.value = validOrderDocs[0]?.order_filter || 'all'
    }
    return
  }
  const validDocKeys = visibleCurrentGroupDocs.value.map((doc) => doc.doc_key)
  if (!validDocKeys.includes(activeDocKey.value)) {
    activeDocKey.value = visibleCurrentGroupDocs.value[0]?.doc_key || ''
  }
}

const displayedIssueCount = computed(() =>
  defectList.value.length > 0 ? defectList.value.length : reviewItemList.value.length,
)

const recordInitial = computed(() => safeText(props.record?.patient_name).charAt(0) || '病')

/**
 * HTML 净化：移除 script/iframe/事件属性，防止 XSS
 * 生产环境建议替换为 DOMPurify 等专业库
 */
const sanitizeHtml = (html: string): string => {
  if (!html) return ''
  return (
    html
      // 移除 script 标签及内容
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      // 移除 iframe
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
      .replace(/<iframe[^>]*\/>/gi, '')
      // 移除事件属性（on*="...")
      .replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\son\w+\s*=\s*[^\s>]*/gi, '')
      // 移除 javascript: 协议
      .replace(/href\s*=\s*["']javascript:[^"']*["']/gi, 'href="#"')
  )
}

// 状态样式计算
const statusClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved')
    return 'bg-emerald-50 text-emerald-600 border-emerald-100'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-50 text-rose-600 border-rose-100'
  return 'bg-amber-50 text-amber-600 border-amber-100'
})

const statusDotClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved') return 'bg-emerald-500'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-500'
  return 'bg-amber-500'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    pending: '待质控',
    urged: '已催办',
    remediated: '已整改',
    approved: '已通过',
    rejected: '已驳回',
    completed: '已通过',
    passed: '已通过',
    failed: '未通过',
  }
  return map[props.record?.status || ''] || props.record?.status || '-'
})

const getScoreColor = (score?: number) => {
  if (!score) return '#94a3b8'
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#f43f5e'
}

const getDefectStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    urged: '已催办',
    remediated: '已整改',
    approved: '已通过',
    rejected: '已驳回',
  }
  return map[status] || status
}

const getReviewStatusText = (status: ReviewIssueItem['status']) => {
  const map: Record<ReviewIssueItem['status'], string> = {
    non_compliant: '不合规',
    uncertain: '待复核',
    compliant: '合规',
    not_applicable: '不适用',
  }
  return map[status] || status
}

const getReviewStatusClass = (status: ReviewIssueItem['status']) => {
  const map: Record<ReviewIssueItem['status'], string> = {
    non_compliant: 'bg-rose-50 text-rose-600 border-rose-100',
    uncertain: 'bg-amber-50 text-amber-600 border-amber-100',
    compliant: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    not_applicable: 'bg-slate-100 text-slate-500 border-slate-200',
  }
  return map[status] || map.uncertain
}

// 加载缺陷列表
const loadDefects = async () => {
  if (!props.record?.record_id) return
  defectLoading.value = true
  try {
    const res = await getDefectList({ record_id: props.record.record_id })
    if (res.success && res.data) {
      defectList.value = (res.data as any).items || (res.data as any) || []
    }
  } catch {
    defectList.value = []
  } finally {
    defectLoading.value = false
  }
}

// 加载病历文书详情
const loadRecordDetail = async () => {
  if (!props.record?.record_id) return
  docLoading.value = true
  try {
    const res = await getRecordDetail(props.record.record_id)
    if (res.success && res.data) {
      const detail = res.data as Record<string, unknown>
      recordDetail.value = detail
      const inlineDefects = detail.defects
      if (Array.isArray(inlineDefects)) {
        defectList.value = inlineDefects as DefectItem[]
      }
      const reviewItems = detail.review_items
      if (Array.isArray(reviewItems)) {
        reviewItemList.value = reviewItems as ReviewIssueItem[]
      }
    }
  } catch {
    recordDetail.value = null
    reviewItemList.value = []
  } finally {
    docLoading.value = false
  }
}

// 操作完成后刷新
const handleActionDone = () => {
  loadDefects()
  emit('refresh')
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

watch([displayDocGroups, visibleCurrentGroupDocs, courseSubtypeOptions], () => {
  syncActiveDocumentSelection()
})

watch(activeDocGroup, (groupKey) => {
  if (groupKey !== 'course') {
    activeCourseSubtype.value = 'all'
  }
  if (groupKey !== 'orders') {
    orderKeyword.value = ''
  }
})

watch(sidebarDocFilter, (groupKey) => {
  if (groupKey === 'all') return
  ensureSidebarGroupExpanded(groupKey)
})

watch([activeHighlightBlockKey, currentDocAllBlocks], async ([blockKey, blocks]) => {
  if (!blockKey || !blocks.some((block) => block.key === blockKey)) return
  await nextTick()
  const el = highlightBlockElements.get(blockKey)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
})

// 打开时自动加载
watch(
  () => props.visible,
  (val) => {
    if (val && props.record) {
      selectedDefectId.value = null
      selectedReviewIssueId.value = null
      activeDocGroup.value = 'all'
      activeCourseSubtype.value = 'all'
      activeDocKey.value = ''
      orderOverviewFilter.value = 'all'
      orderKeyword.value = ''
      sidebarDocFilter.value = 'all'
      expandedSidebarGroups.value = ['course']
      activeHighlightTarget.value = null
      highlightBlockElements.clear()
      recordDetail.value = null
      reviewItemList.value = []
      loadDefects()
      loadRecordDetail()
    }
  },
)
</script>

<style scoped>
.qc-review-drawer :deep(.ant-drawer-content) {
  background: #f5f7fa;
}

.qc-review-drawer :deep(.ant-drawer-header) {
  display: none;
}

.qc-review-drawer :deep(.ant-drawer-body) {
  padding: 24px;
  background: #f5f7fa;
}

.review-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: calc(100vh - 72px);
}

.review-summary {
  border: 1px solid #e8edf5;
  border-radius: 20px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
  padding: 24px;
}

.review-summary__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.review-summary__identity {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  min-width: 0;
}

.review-summary__avatar {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
  color: #2563eb;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  flex-shrink: 0;
}

.review-summary__identity-main {
  min-width: 0;
}

.review-summary__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.review-summary__title {
  margin: 0;
  font-size: 24px;
  line-height: 1.3;
  font-weight: 700;
  color: #172554;
}

.review-summary__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
}

.review-summary__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.review-summary__patient-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.review-summary__patient-name {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.review-summary__patient-meta,
.review-summary__hint,
.review-summary__actions-label,
.review-panel__desc,
.review-content__meta,
.review-content__time,
.review-empty__desc,
.review-issue-card__meta,
.review-issue-card__confidence {
  color: #7b8aa5;
}

.review-summary__hint {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
}

.review-summary__actions {
  min-width: 180px;
  border-radius: 16px;
  border: 1px solid #e8edf5;
  background: rgba(248, 250, 252, 0.9);
  padding: 14px 16px;
}

.review-summary__actions-label {
  font-size: 12px;
}

.review-summary__actions-value {
  margin-top: 6px;
  font-size: 14px;
  color: #1e293b;
  font-weight: 600;
}

.review-metrics {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.review-metric-card {
  border: 1px solid #e8edf5;
  border-radius: 18px;
  background: #fff;
  padding: 16px 18px;
}

.review-metric-card__label {
  font-size: 12px;
  color: #7b8aa5;
}

.review-metric-card__value {
  margin-top: 8px;
  font-size: 18px;
  line-height: 1.4;
  font-weight: 600;
  color: #1e293b;
  word-break: break-word;
}

.review-metric-card__value--mono {
  font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
}

.review-workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr) 372px;
  gap: 18px;
}

.review-sidebar,
.review-content,
.review-issues {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #e8edf5;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.review-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid #eef2f7;
}

.review-panel__title {
  font-size: 16px;
  line-height: 1.4;
  font-weight: 700;
  color: #172554;
}

.review-panel__desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
}

.review-card__title,
.review-alert__title,
.review-empty__title,
.review-issue-card__title {
  color: #1e293b;
}

.review-sidebar__toolbar {
  padding: 16px 16px 14px;
  border-bottom: 1px solid #eef2f7;
  background: #fbfdff;
}

.review-sidebar__select-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-sidebar__select-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.review-sidebar__select {
  width: 100%;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #fff;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.5;
  padding: 10px 12px;
  outline: none;
}

.review-sidebar__select:focus {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.review-sidebar__list,
.review-content__body,
.review-issues__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.review-sidebar__list {
  padding: 10px 0 16px;
  background: linear-gradient(180deg, #fcfdff 0%, #ffffff 100%);
}

.review-tree-group + .review-tree-group {
  margin-top: 2px;
}

.review-tree-node,
.review-tree-doc {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  transition:
    background-color 0.2s ease,
    color 0.2s ease;
  outline: none;
}

.review-tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  color: #1e293b;
  font-size: 14px;
  line-height: 1.6;
}

.review-tree-node:hover,
.review-tree-doc:hover {
  background: #f8fbff;
}

.review-tree-node--root {
  padding-top: 6px;
}

.review-tree-node--active,
.review-tree-doc--active {
  color: #2563eb;
  background: #eff6ff;
}

.review-tree-node__caret,
.review-tree-node__spacer {
  width: 12px;
  flex-shrink: 0;
  color: #94a3b8;
  text-align: center;
}

.review-tree-node__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-tree-children {
  padding: 2px 0 6px 0;
}

.review-tree-doc {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  padding: 7px 18px 7px 38px;
  color: #334155;
  font-size: 13px;
  line-height: 1.65;
}

.review-tree-doc__date {
  color: #64748b;
  white-space: nowrap;
}

.review-tree-doc__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-card__title,
.review-card__title,
.review-content__header {
  align-items: center;
}

.review-content__header-main {
  min-width: 0;
}

.review-content__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.review-content__type-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
}

.review-content__title {
  margin: 10px 0 0;
  font-size: 24px;
  line-height: 1.4;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}

.review-content__meta {
  margin-top: 8px;
  font-size: 13px;
}

.review-content__flags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.review-flag {
  border-radius: 999px;
  border: 1px solid #fcd34d;
  background: #fffbeb;
  color: #b45309;
  padding: 6px 10px;
  font-size: 12px;
}

.review-content__body {
  padding: 20px;
  background: #f8fafc;
}

.review-card {
  border: 1px solid #e8edf5;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.03);
}

.review-card + .review-card,
.review-alert + .review-card,
.review-card + .review-empty,
.review-alert + .review-empty,
.review-alert + .review-card--content,
.review-card--fields + .review-card--content {
  margin-top: 16px;
}

.review-card__title {
  font-size: 15px;
  font-weight: 700;
  padding: 18px 20px 0;
}

.review-structured-list {
  padding: 10px 0;
}

.review-structured-row {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 18px;
  padding: 12px 20px;
  border-top: 1px solid #eef2f7;
}

.review-structured-row:first-child {
  border-top: 0;
}

.review-structured-row__label {
  font-size: 14px;
  line-height: 1.9;
  color: #64748b;
  word-break: break-word;
}

.review-structured-row__content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.order-overview {
  overflow: hidden;
}

.order-overview__summary {
  display: flex;
  align-items: stretch;
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid #eef2f7;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.order-overview__stat {
  min-width: 96px;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  background: #fff;
  padding: 10px 12px;
}

.order-overview__stat span {
  display: block;
  font-size: 12px;
  color: #64748b;
}

.order-overview__stat strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
  color: #172554;
}

.order-overview__range {
  display: flex;
  align-items: center;
  min-width: 220px;
  color: #475569;
  font-size: 13px;
}

.order-overview__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 18px;
  border-bottom: 1px solid #eef2f7;
  background: #fbfdff;
}

.order-overview__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.order-overview__filter {
  border: 1px solid #dbe4f0;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  cursor: pointer;
}

.order-overview__filter--active {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #2563eb;
}

.order-overview__search {
  width: 240px;
  max-width: 100%;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #fff;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 12px;
  outline: none;
}

.order-overview__search:focus {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.order-overview__table-scroll {
  overflow-x: auto;
}

.order-overview__table {
  width: 100%;
  min-width: 820px;
  border-collapse: collapse;
  font-size: 13px;
  color: #334155;
}

.order-overview__table th,
.order-overview__table td {
  border-bottom: 1px solid #eef2f7;
  padding: 10px 12px;
  vertical-align: top;
  text-align: left;
  line-height: 1.55;
}

.order-overview__table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.order-overview__table tbody tr:hover {
  background: #f8fbff;
}

.order-overview__row--active {
  background: #fff7d6;
  box-shadow: inset 3px 0 0 #f59e0b;
}

.order-overview__time {
  white-space: nowrap;
  color: #475569;
}

.order-overview__content {
  min-width: 220px;
  font-weight: 600;
  color: #1e293b;
}

.order-overview__tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.order-overview__tag--muted {
  background: #f8fafc;
  color: #64748b;
}

.order-overview__empty {
  margin: 18px;
}

.review-alert {
  border: 1px solid #fde68a;
  border-radius: 16px;
  background: #fffbeb;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.review-alert__title {
  font-size: 13px;
  font-weight: 700;
  color: #92400e;
}

.review-alert__desc {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.7;
  color: #b45309;
}

.review-paragraph {
  border-radius: 10px;
  padding: 0;
  background: transparent;
  border: 0;
}

.review-paragraph + .review-paragraph {
  margin-top: 10px;
}

.review-paragraph--inline {
  margin-top: 0;
}

.review-empty {
  min-height: 220px;
  border: 1px dashed #d9e2ef;
  border-radius: 18px;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px;
}

.review-empty--sidebar,
.review-empty--issues {
  min-height: 180px;
}

.review-empty__icon {
  font-size: 36px;
  color: #94a3b8;
  margin-bottom: 12px;
}

.review-empty__title {
  font-size: 14px;
  font-weight: 600;
}

.review-empty__desc {
  margin-top: 6px;
  font-size: 12px;
}

.review-issues__reload {
  color: #64748b;
}

.review-issue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 18px 22px;
}

.review-issue-card {
  border: 1px solid #e8edf5;
  border-radius: 18px;
  background: #fff;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.review-issue-card:hover,
.review-issue-card--active {
  border-color: #93c5fd;
  box-shadow: 0 10px 24px rgba(59, 130, 246, 0.12);
}

.review-issue-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.review-issue-card__top--start {
  align-items: flex-start;
}

.review-issue-card__title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.review-issue-card__title-block {
  min-width: 0;
}

.review-issue-card__title {
  font-size: 14px;
  line-height: 1.6;
  font-weight: 700;
  word-break: break-word;
}

.review-issue-card__dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 999px;
  flex-shrink: 0;
  background: #3b82f6;
}

.review-issue-card__dot--critical {
  background: #f43f5e;
}

.review-issue-card__dot--warning {
  background: #f59e0b;
}

.review-issue-card__dot--info {
  background: #3b82f6;
}

.review-issue-card__status,
.review-issue-card__pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
}

.review-issue-card__status--pending {
  background: #fff7ed;
  color: #c2410c;
}

.review-issue-card__status--urged {
  background: #eff6ff;
  color: #2563eb;
}

.review-issue-card__status--approved {
  background: #ecfdf5;
  color: #059669;
}

.review-issue-card__status--rejected {
  background: #fff1f2;
  color: #e11d48;
}

.review-issue-card__status--remediated {
  background: #f1f5f9;
  color: #64748b;
}

.review-issue-card__summary,
.review-issue-card__section {
  font-size: 13px;
  line-height: 1.75;
  color: #475569;
}

.review-issue-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
}

.review-issue-card__actions {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #eef2f7;
}

.review-issue-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.review-issue-card__pill--plain {
  background: #f8fafc;
  color: #64748b;
  border-color: #e2e8f0;
}

.review-issue-card__section + .review-issue-card__section {
  margin-top: 8px;
}

.review-issue-card__section-label {
  color: #94a3b8;
  margin-right: 8px;
}

.review-issue-card__section--suggestion {
  color: #2563eb;
}

.doc-content {
  font-size: 14px;
  line-height: 1.95;
  color: #334155;
}

.doc-content--prewrap {
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-content--active-highlight {
  background: #fff7d6;
  border-color: #f3d57a;
  box-shadow: inset 0 0 0 1px #f3d57a;
}

.doc-content :deep(.doc-content__mark) {
  background: #fde68a;
  color: #7c2d12;
  border-radius: 4px;
  padding: 0 2px;
}

.qc-review-drawer button:focus-visible {
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 1680px) {
  .review-workspace {
    grid-template-columns: 272px minmax(0, 1fr) 340px;
  }

  .review-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1440px) {
  .review-workspace {
    grid-template-columns: 260px minmax(0, 1fr);
  }

  .review-issues {
    grid-column: 1 / -1;
    min-height: 320px;
  }

  .review-summary__top {
    flex-direction: column;
  }
}

@media (max-width: 1100px) {
  .review-metrics,
  .review-workspace {
    grid-template-columns: 1fr;
  }

  .review-sidebar,
  .review-issues {
    min-height: 280px;
  }

  .review-structured-row {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .review-tree-doc {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .order-overview__toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .order-overview__search {
    width: 100%;
  }
}
</style>
