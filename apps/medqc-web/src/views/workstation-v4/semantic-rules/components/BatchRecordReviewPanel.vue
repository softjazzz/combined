<template>
  <section class="record-review mq-card" data-testid="batch-record-review">
    <header class="record-review__head">
      <div>
        <h3 class="record-review__title">按病历查看结果</h3>
        <p v-if="confirmedOnly" class="record-review__desc">本面板展示 {{ records.length }} 份有确定问题的病历。</p>
        <p v-else class="record-review__desc">
          共 {{ records.length }} 份病历，{{ issueRecordCount }} 份发现问题；问题多的病历排在前面。
        </p>
      </div>
    </header>

    <div class="record-review__body">
      <aside class="record-review__list mq-inset">
        <input
          v-model="keyword"
          class="mq-input record-review__search"
          placeholder="搜索住院号、科室或病历序号"
          data-testid="record-review-search"
        />
        <div class="mq-segmented mq-segmented--sm record-review__scope">
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': scope === 'issues' }"
            @click="scope = 'issues'"
          >
            有问题 {{ issueRecordCount }}
          </button>
          <button
            v-if="!confirmedOnly"
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': scope === 'all' }"
            @click="scope = 'all'"
          >
            全部 {{ records.length }}
          </button>
        </div>
        <div class="record-review__records">
          <button
            v-for="record in visibleRecords"
            :key="record.key"
            type="button"
            class="record-review__record"
            :class="{ 'is-active': record.key === selectedRecord?.key }"
            :data-testid="`record-review-record-${record.sequence}`"
            @click="selectRecord(record.key)"
          >
            <span class="record-review__record-title">
              {{ record.title
              }}<template v-if="record.department"> · {{ record.department }}</template>
            </span>
            <span class="record-review__record-meta">{{ recordMeta(record) }}</span>
            <span class="record-review__record-counts">
              <span :class="{ 'is-danger': record.counts.non_compliant > 0 }"
                >问题 {{ record.counts.non_compliant }}</span
              >
              <span v-if="!confirmedOnly" :class="{ 'is-warning': record.counts.data_gap > 0 }"
                >待补 {{ record.counts.data_gap }}</span
              >
            </span>
          </button>
          <p v-if="!visibleRecords.length" class="record-review__empty">{{ confirmedOnly ? '当前没有可展示的确定问题' : '没有符合条件的病历' }}</p>
        </div>
      </aside>

      <div v-if="selectedRecord" class="record-review__detail">
        <div class="record-review__detail-head">
          <div>
            <h4>
              {{ selectedRecord.title
              }}<template v-if="selectedRecord.department">
                · {{ selectedRecord.department }}
              </template>
            </h4>
            <p>{{ recordDetailMeta(selectedRecord) }}</p>
          </div>
        </div>

        <div class="mq-segmented record-review__status-tabs" role="tablist">
          <button
            v-for="status in statusTabs"
            :key="status"
            type="button"
            role="tab"
            class="mq-segmented__item"
            :class="{ 'is-active': activeStatus === status }"
            :aria-selected="activeStatus === status"
            :data-testid="`record-review-tab-${status}`"
            @click="activeStatus = status"
          >
            {{ REVIEW_STATUS_LABELS[status] }} {{ selectedRecord.counts[status] }}
          </button>
        </div>

        <template v-if="chapterGroups.length">
          <section
            v-for="group in chapterGroups"
            :key="group.chapter"
            class="record-review__chapter"
          >
            <div class="record-review__chapter-title">
              {{ group.chapter }} · {{ group.items.length }} 条
            </div>
            <article
              v-for="item in group.items"
              :key="item.key"
              class="record-review__item mq-inset"
              :class="{ 'is-expanded': expandedKeys.has(item.key) }"
            >
              <button
                type="button"
                class="record-review__item-head"
                :aria-expanded="expandedKeys.has(item.key)"
                @click="toggleItem(item.key)"
              >
                <span class="record-review__item-title">{{ item.title }}</span>
                <span class="mq-status" :class="statusClass(item.status)">{{
                  STATUS_PILL_LABELS[item.status]
                }}</span>
              </button>
              <p v-if="item.summary" class="record-review__item-summary">
                {{ item.summary }}
              </p>
              <div v-if="expandedKeys.has(item.key)" class="record-review__item-detail">
                <div v-if="item.evidence.length" class="record-review__evidence mq-soft">
                  <span class="record-review__label">依据</span>
                  <div
                    v-for="evidence in item.evidence"
                    :key="evidence.key"
                    class="record-review__evidence-row"
                  >
                    <strong>{{ evidence.source }}</strong>
                    <span v-if="evidence.time">{{ evidence.time }}</span>
                    <q v-if="evidence.quote">{{ evidence.quote }}</q>
                  </div>
                </div>
                <p v-if="item.suggestion" class="record-review__suggestion">
                  <span class="record-review__label">修改建议</span>
                  {{ item.suggestion }}
                </p>
                <span class="record-review__rule-code mq-mono">{{ item.ruleCode }}</span>
              </div>
              <button type="button" class="record-review__toggle" @click="toggleItem(item.key)">
                {{ expandedKeys.has(item.key) ? '收起' : '查看依据和建议' }}
              </button>
            </article>
          </section>
        </template>
        <p v-else class="record-review__empty">
          这份病历没有“{{ REVIEW_STATUS_LABELS[activeStatus] }}”类结果。
        </p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  groupByChapter,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_ORDER,
  REVIEW_STATUS_TONES,
  type ReviewRecord,
  type ReviewStatusKey,
} from '@/views/workstation-v4/semantic-rules/batchRecordReviewModel'

const props = defineProps<{
  records: ReviewRecord[]
  confirmedOnly?: boolean
}>()

const STATUS_PILL_LABELS: Record<ReviewStatusKey, string> = {
  non_compliant: '确定问题',
  data_gap: '需补资料',
  compliant: '合格',
  not_applicable: '不适用',
  pending: '未完成判定',
}

const keyword = ref('')
const scope = ref<'issues' | 'all'>('issues')
const selectedKey = ref('')
const activeStatus = ref<ReviewStatusKey>('non_compliant')
const expandedKeys = ref(new Set<string>())

const issueRecordCount = computed(
  () => props.records.filter((record) => record.counts.non_compliant > 0).length,
)

const visibleRecords = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return props.records.filter((record) => {
    if (
      scope.value === 'issues' &&
      record.counts.non_compliant === 0 &&
      issueRecordCount.value > 0
    ) {
      return false
    }
    if (!text) return true
    return [record.title, record.department, record.inpatientNo, String(record.sequence)].some(
      (value) => value.toLowerCase().includes(text),
    )
  })
})

const selectedRecord = computed(
  () =>
    props.records.find((record) => record.key === selectedKey.value) ||
    visibleRecords.value[0] ||
    props.records[0] ||
    null,
)

// “未完成判定”只在有时出现，避免给客户制造没有内容的分类。
const statusTabs = computed(() =>
  REVIEW_STATUS_ORDER.filter(
    (status) => props.confirmedOnly ? status === 'non_compliant' : status !== 'pending' || (selectedRecord.value?.counts.pending || 0) > 0,
  ),
)

const chapterGroups = computed(() =>
  groupByChapter(
    (selectedRecord.value?.items || []).filter((item) => item.status === activeStatus.value),
  ),
)

function defaultStatus(record: ReviewRecord | null): ReviewStatusKey {
  if (props.confirmedOnly || !record) return 'non_compliant'
  return (
    REVIEW_STATUS_ORDER.find((status) => record.counts[status] > 0 && status !== 'pending') ||
    'non_compliant'
  )
}

watch(
  () => [selectedRecord.value?.key, props.confirmedOnly],
  () => {
    activeStatus.value = defaultStatus(selectedRecord.value)
    expandedKeys.value = new Set()
  },
  { immediate: true },
)

function selectRecord(key: string) {
  selectedKey.value = key
}

function toggleItem(key: string) {
  const next = new Set(expandedKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedKeys.value = next
}

function statusClass(status: ReviewStatusKey) {
  const tone = REVIEW_STATUS_TONES[status]
  return tone === 'neutral' ? '' : `mq-status--${tone}`
}

function recordMeta(record: ReviewRecord) {
  return (
    [
      record.inpatientNo ? `住院号 ${record.inpatientNo}` : '',
      record.dischargeDate ? `${record.dischargeDate.slice(5)} 出院` : '',
    ]
      .filter(Boolean)
      .join(' · ') || '病历标识暂不可用'
  )
}

function recordDetailMeta(record: ReviewRecord) {
  return (
    [
      record.inpatientNo ? `住院号 ${record.inpatientNo}` : '',
      record.admissionDate ? `${record.admissionDate} 入院` : '',
      record.dischargeDate ? `${record.dischargeDate} 出院` : '',
      record.doctor ? `主治 ${record.doctor}` : '',
    ]
      .filter(Boolean)
      .join(' · ') || '病历标识暂不可用，可按序号与任务病历清单对应'
  )
}
</script>

<style scoped src="./styles/batch-record-review.css"></style>
