<template>
  <div class="record-review-todo">
    <a-page-header
      title="病历审核待办"
      sub-title="本人受领任务中结果可用、尚未审核的病历"
      class="bg-white mb-4 shadow-sm"
    />

    <div class="px-6 pb-6">
      <a-card
        :bordered="false"
        class="shadow-sm"
      >
        <!-- 筛选 -->
        <div class="record-review-todo__toolbar">
          <div class="record-review-todo__filters">
            <a-radio-group
              :value="stage ?? 'all'"
              button-style="solid"
              data-testid="record-review-stage-filter"
              @change="(event: RadioChangeEvent) => void changeQuery({ stage: event.target.value })"
            >
              <a-radio-button
                v-for="option in stageOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </a-radio-button>
            </a-radio-group>
            <a-select
              :value="scene"
              :options="sceneOptions"
              style="width: 140px"
              data-testid="record-review-scene-filter"
              @change="(value: unknown) => void changeQuery({ scene: value })"
            />
          </div>
          <div class="record-review-todo__summary">
            <span v-if="total !== null">共 {{ total }} 份</span>
            <a-button
              :loading="loading"
              data-testid="record-review-todo-refresh"
              @click="void fetchList()"
            >
              刷新
            </a-button>
          </div>
        </div>

        <a-alert
          v-if="listError"
          type="error"
          :message="listError"
          show-icon
          class="mb-4"
          data-testid="record-review-todo-error"
        >
          <template #action>
            <a-button
              size="small"
              @click="void fetchList()"
            >
              重试
            </a-button>
          </template>
        </a-alert>

        <template v-else>
          <p
            v-if="loading && !items.length"
            class="record-review-todo__muted"
          >
            正在读取审核待办…
          </p>
          <a-empty
            v-else-if="!items.length"
            description="当前没有待审核的病历"
          />
          <div
            v-else
            class="record-review-todo__list"
          >
            <article
              v-for="item in items"
              :key="`${item.task_id}:${item.task_record_id}:${item.run_number}`"
              class="record-review-todo__item"
              data-testid="record-review-todo-item"
            >
              <div class="record-review-todo__main">
                <header>
                  <strong>机构 {{ known(item.institute_id) }} / 患者 {{ known(item.patient_id) }} / 就诊 {{ known(item.visit_id) }}</strong>
                  <a-tag :color="item.stage === 'recheck' ? 'warning' : 'processing'">
                    {{ item.stage === 'recheck' ? '待复审' : '待初审' }}
                  </a-tag>
                </header>
                <p>
                  任务：{{ item.task_name || item.task_id }} · {{ taskSceneLabel(item.task_scene) }} · 第 {{ item.run_number }} 次运行
                </p>
                <p class="record-review-todo__muted">
                  规则集：{{ known(item.rule_set_key) }} · {{ known(item.rule_set_version) }}
                </p>
              </div>
              <a-button
                type="primary"
                :data-testid="`record-review-go-${item.task_record_id}`"
                @click="void goReview(item)"
              >
                去审核
              </a-button>
            </article>
          </div>

          <div
            v-if="total !== null && total > pageSize"
            class="record-review-todo__pagination"
          >
            <a-pagination
              :current="page"
              :page-size="pageSize"
              :total="total"
              :show-size-changer="false"
              @change="(value: number) => void changePage(value)"
            />
          </div>
        </template>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RadioChangeEvent } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import { getRecordReviewTodos } from '@/api/recordReviews'
import type { RecordReviewStage, RecordReviewTodoItem } from '@/api/recordReviews'
import type { DashboardScene } from '@/api/dashboard'

const route = useRoute()
const router = useRouter()

const stageOptions = [
  { value: 'all', label: '全部' },
  { value: 'initial', label: '待初审' },
  { value: 'recheck', label: '待复审' },
]
const sceneOptions: Array<{ value: DashboardScene; label: string }> = [
  { value: 'all', label: '全部场景' },
  { value: 'outpatient_emergency', label: '门急诊' },
  { value: 'running', label: '运行病历' },
  { value: 'final', label: '终末病历' },
]

const pageSize = 20
const items = ref<RecordReviewTodoItem[]>([])
const total = ref<number | null>(null)
const page = ref(1)
const loading = ref(false)
const listError = ref('')
let listSequence = 0

const stage = computed<RecordReviewStage | undefined>(() => parseStage(route.query.stage))
const scene = computed<DashboardScene>(() => parseScene(route.query.scene))

function parseStage(value: unknown): RecordReviewStage | undefined {
  return value === 'initial' || value === 'recheck' ? value : undefined
}

function parseScene(value: unknown): DashboardScene {
  return sceneOptions.some((option) => option.value === value) ? value as DashboardScene : 'all'
}

function known(value: string | null | undefined) {
  return value && String(value).trim() ? value : '未知'
}

function taskSceneLabel(value: string | null) {
  return ({ running: '运行', final: '终末', outpatient: '门急诊' } as Record<string, string>)[value || ''] || '场景未知'
}

async function fetchList() {
  const query = { stage: stage.value, scene: scene.value, page: page.value, page_size: pageSize }
  const token = ++listSequence
  loading.value = true
  listError.value = ''
  try {
    const response = await getRecordReviewTodos(query)
    if (token !== listSequence) return
    const data = response.data
    if (!response.success || !data || !Array.isArray(data.items)
      || !Number.isInteger(data.total) || data.total < 0) {
      items.value = []
      total.value = null
      listError.value = response.status === 403
        ? '没有查看病历审核待办的权限'
        : response.message || '读取病历审核待办失败'
      return
    }
    items.value = data.items
    total.value = data.total
  } catch {
    if (token !== listSequence) return
    items.value = []
    total.value = null
    listError.value = '网络异常或服务器不可用'
  } finally {
    if (token === listSequence) loading.value = false
  }
}

async function changeQuery(next: { stage?: unknown; scene?: unknown }) {
  const query = { ...route.query }
  if ('stage' in next) {
    const value = parseStage(next.stage)
    if (value) query.stage = value
    else delete query.stage
  }
  if ('scene' in next) {
    const value = parseScene(next.scene)
    if (value === 'all') delete query.scene
    else query.scene = value
  }
  await router.replace({ query })
}

async function changePage(value: number) {
  page.value = value
  await fetchList()
}

/** 跳转到“我的任务”，由任务详情抽屉定位到该病历与运行。 */
async function goReview(item: RecordReviewTodoItem) {
  await router.push({
    path: '/dashboard/tasks/my',
    query: {
      task_id: item.task_id,
      task_record_id: item.task_record_id,
      run_number: String(item.run_number),
      scene: item.task_scene || scene.value,
      stage: item.stage,
    },
  })
}

watch([stage, scene], () => {
  page.value = 1
  void fetchList()
}, { immediate: true })
</script>

<style scoped>
.record-review-todo__toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.record-review-todo__filters, .record-review-todo__summary { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.record-review-todo__summary { color: rgba(29, 29, 31, .6); font-size: 13px; }
.record-review-todo__list { display: grid; gap: 12px; }
.record-review-todo__item { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid #f0f0f0; border-radius: 10px; background: #fff; }
.record-review-todo__main { min-width: 0; }
.record-review-todo__main header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; overflow-wrap: anywhere; }
.record-review-todo__main p { margin: 6px 0 0; line-height: 22px; overflow-wrap: anywhere; }
.record-review-todo__pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.record-review-todo__muted { color: rgba(29, 29, 31, .6); font-size: 13px; }
</style>
