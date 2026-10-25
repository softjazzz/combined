<template>
  <section
    v-if="allowed"
    class="case-inbox mq-page"
  >
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <h2 class="mq-page-title">
          病历沟通
        </h2>
      </div>
      <router-link
        class="mq-btn"
        to="/workstation-v5/worklist?assist=message"
      >
        消息面板
      </router-link><a-button
        :disabled="loading"
        aria-label="刷新病历沟通"
        @click="load()"
      >
        <template #icon>
          <MqIcon
            name="sync"
            :size="16"
          />
        </template>
      </a-button>
    </header>
    <a-alert
      v-if="error"
      :message="error"
      type="error"
      show-icon
    />
    <a-spin :spinning="loading">
      <ul>
        <li
          v-for="item in items"
          :key="item.id"
        >
          <button
            type="button"
            @click="show(item.id)"
          >
            <span>{{ item.department }} · {{ item.visit_id }} · {{ labels[item.action] }}</span><span>{{ item.withdrawn ? '已撤回' : item.is_read ? '已读' : '未读' }}</span><span>{{ item.content }}</span>
          </button>
        </li>
      </ul>
      <p v-if="!loading && !error && !items.length">
        暂无病历沟通
      </p>
    </a-spin>
    <a-pagination
      v-if="total && !error"
      v-model:current="page"
      :total="total"
      :page-size="20"
      :show-size-changer="false"
      @change="load(false)"
    />
    <a-drawer
      :open="detailOpen"
      title="病历沟通"
      width="min(620px, 100vw)"
      :root-style="{ zIndex: 1300 }"
      @close="close"
    >
      <a-alert
        v-if="detailError"
        :message="detailError"
        type="error"
        show-icon
      /><a-button
        v-if="detailError"
        :disabled="detailLoading"
        @click="refreshDetail"
      >
        刷新核对
      </a-button>
      <a-spin :spinning="detailLoading">
        <template v-if="selected">
          <a-descriptions
            :column="1"
            bordered
          >
            <a-descriptions-item label="病历">
              {{ selected.visit_id }} ·
              {{ selected.scene === 'running' ? '运行病历' : '终末病历' }}
            </a-descriptions-item><a-descriptions-item label="冻结结果">
              {{ selected.root_job_id }} / {{ selected.envelope_id }}
            </a-descriptions-item><a-descriptions-item label="规则版本">
              {{ selected.rule_set_key }} · {{ selected.rule_set_version }}
            </a-descriptions-item><a-descriptions-item label="通知状态">
              {{
                selected.withdrawn ? '原催办已撤回' : selected.is_read ? '已读' : '未读'
              }}
            </a-descriptions-item>
          </a-descriptions>
          <h3>{{ labels[selected.action] }}</h3>
          <p class="case-inbox__content">
            {{ selected.content }}
          </p>
          <h3>操作历史</h3>
          <ol class="case-inbox__history">
            <li
              v-for="event in selected.history"
              :key="event.id"
              :class="{ 'case-inbox__active': event.id === selected.id }"
            >
              <strong>{{ labels[event.action] }} ·
                {{ event.withdrawn ? '已撤回' : event.is_read ? '已读' : '未读' }}</strong><time>{{ formatTime(event.created_at) }}</time>
              <p>{{ event.content }}</p>
              <p
                v-if="event.related_event_id"
                class="case-inbox__reference"
              >
                原催办：{{ event.related_event_id }}
              </p>
            </li>
          </ol>
        </template>
      </a-spin>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MqIcon from '@/components/icons/MqIcon.vue'
import { formatDateTime as formatTime } from '@/utils/date'
import { useAuthStore } from '@/stores/auth'
import {
  getCommunication,
  getCommunicationInbox,
  readCommunication,
} from '@/api/caseCommunications'
import type { Communication, CommunicationDetail } from '@/api/caseCommunications'

const auth = useAuthStore()
const route = useRoute()
const allowed = computed(() => auth.userRoles.includes('doctor'))
const items = ref<Communication[]>([]),
  selected = ref<CommunicationDetail>()
const loading = ref(false),
  error = ref(''),
  detailError = ref(''),
  detailOpen = ref(false),
  detailLoading = ref(false)
const page = ref(1),
  total = ref(0)
let generation = 0,
  detailGeneration = 0,
  activeId = ''
const labels = { urge: '病历催办', opinion: '质控意见', withdraw: '催办撤回' }
async function load(reset = true) {
  if (!allowed.value) return
  const token = ++generation
  loading.value = true
  error.value = ''
  if (reset) page.value = 1
  try {
    const data = await getCommunicationInbox(page.value)
    if (token !== generation) return
    items.value = data.items
    total.value = data.total
  } catch (reason) {
    if (token === generation) {
      error.value = reason instanceof Error ? reason.message : '读取失败'
      items.value = []
    }
  } finally {
    if (token === generation) loading.value = false
  }
}
function validateDetail(data: CommunicationDetail, id: string) {
  if (
    data.id !== id ||
    !data.notification_id ||
    !Array.isArray(data.history) ||
    !data.history.some((item) => item.id === id)
  )
    throw new Error('消息来源不一致，请刷新核对')
}
async function show(id: string) {
  if (!allowed.value || !id) return
  const token = ++detailGeneration
  activeId = id
  detailOpen.value = true
  selected.value = undefined
  detailError.value = ''
  detailLoading.value = true
  try {
    // 详情授权成功后才发送已读，不从列表旧对象推断接收权限。
    const detail = await getCommunication(id)
    if (token !== detailGeneration) return
    validateDetail(detail, id)
    selected.value = detail
    const data = await readCommunication(id)
    if (token !== detailGeneration) return
    validateDetail(data, id)
    if (!data.is_read) throw new Error('已读结果无法确认，请刷新核对')
    selected.value = data
    items.value = items.value.map((value) => (value.id === id ? data : value))
  } catch (reason) {
    if (token === detailGeneration)
      detailError.value = reason instanceof Error ? reason.message : '已读结果待核实'
  } finally {
    if (token === detailGeneration) detailLoading.value = false
  }
}
async function refreshDetail() {
  if (!activeId || detailLoading.value) return
  const token = ++detailGeneration,
    id = activeId
  detailLoading.value = true
  try {
    const data = await getCommunication(id)
    if (token !== detailGeneration) return
    validateDetail(data, id)
    selected.value = data
    items.value = items.value.map((value) => (value.id === id ? data : value))
    detailError.value = data.is_read ? '' : '通知仍未读，关闭后重新查看可再次确认'
  } catch (reason) {
    if (token === detailGeneration) {
      selected.value = undefined
      detailError.value = reason instanceof Error ? reason.message : '读取失败'
    }
  } finally {
    if (token === detailGeneration) detailLoading.value = false
  }
}
function close() {
  detailGeneration += 1
  detailOpen.value = false
  detailLoading.value = false
  selected.value = undefined
  activeId = ''
}
function reset() {
  generation += 1
  close()
  items.value = []
  total.value = 0
  page.value = 1
  error.value = ''
  detailError.value = ''
  loading.value = false
}
function openRoute() {
  const id = route.query.communication_id
  if (typeof id === 'string' && id.trim() && allowed.value) void show(id)
}
watch(
  () => [auth.user?.id, auth.user?.institute_id, auth.user?.department, ...auth.userRoles],
  () => {
    reset()
    if (allowed.value) {
      void load()
      openRoute()
    }
  },
  { immediate: true },
)
watch(
  () => route.query.communication_id,
  () => {
    close()
    openRoute()
  },
)
onUnmounted(reset)
</script>

<style scoped>
.case-inbox ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.case-inbox li button {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  width: 100%;
  padding: 14px 0;
  text-align: left;
  background: none;
  border: 0;
  border-bottom: 1px solid var(--mq-border, #edf0f4);
  cursor: pointer;
}
.case-inbox li button span:last-child {
  flex-basis: 100%;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.case-inbox h3 {
  font-size: 16px;
  margin: 22px 0 10px;
}
.case-inbox__content,
.case-inbox__history p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.case-inbox__history {
  padding-left: 22px;
}
.case-inbox__history li {
  padding: 12px 8px;
  border-bottom: 1px solid var(--mq-border, #edf0f4);
}
.case-inbox__history time {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--mq-text-secondary, #667085);
}
.case-inbox__active {
  background: var(--mq-soft-bg, #f2f8fc);
}
.case-inbox__reference {
  font-size: 12px;
  color: var(--mq-text-secondary, #667085);
}
</style>
