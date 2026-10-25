<template>
  <section
    v-if="allowed"
    class="case-inbox mq-page"
  >
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">质控作业 · 医生消息</span>
        <h1 class="mq-page-title">
          病历沟通
        </h1>
      </div>
      <div class="mq-page-head__actions">
        <router-link
          class="mq-btn"
          to="/workstation-v5/worklist?assist=message"
        >
          <MqIcon
            name="task"
            :size="16"
          />消息面板
        </router-link><a-button
          :disabled="loading"
          aria-label="刷新病历沟通"
          title="刷新病历沟通"
          @click="load()"
        >
          <template #icon>
            <MqIcon
              name="sync"
              :size="16"
            />
          </template>
        </a-button>
      </div>
    </header>
    <a-alert
      v-if="error"
      :message="error"
      type="error"
      show-icon
    />
    <section
      class="case-inbox__records"
      aria-label="病历沟通记录"
    >
      <div class="case-inbox__section-head">
        <h2>
          <MqIcon
            name="task"
            :size="18"
          />接收记录
        </h2>
        <span v-if="loading">正在读取</span><span v-else-if="error">数据未核实</span><span v-else>共 {{ total }} 条记录</span>
      </div>
      <a-spin :spinning="loading">
        <ul class="case-inbox__list">
          <li
            v-for="item in items"
            :key="item.id"
          >
            <button
              type="button"
              class="case-inbox__row"
              :class="{ 'is-unread': !item.is_read && !item.withdrawn }"
              :aria-label="`查看${item.visit_id}的${labels[item.action]}消息`"
              @click="show(item.id)"
            >
              <MqIconTile
                :name="communicationIcon(item.action)"
                :size="40"
                :tone="item.action === 'withdraw' ? 'neutral' : 'brand'"
              />
              <span class="case-inbox__row-copy">
                <span class="case-inbox__row-title"><strong>{{ labels[item.action] }}</strong><span
                  class="mq-status"
                  :class="communicationStatusClass(item)"
                >{{
                  communicationStatus(item)
                }}</span></span>
                <span class="case-inbox__row-context"><span>{{ item.visit_id }}</span><span>{{ item.scene === 'running' ? '运行病历' : '终末病历' }}</span><span>{{ item.department }}</span></span>
                <span class="case-inbox__excerpt">{{ item.content }}</span>
              </span>
              <time :datetime="item.created_at">{{ formatTime(item.created_at) }}</time>
              <MqIcon
                class="case-inbox__row-arrow"
                name="back"
                :size="16"
              />
            </button>
          </li>
        </ul>
        <div
          v-if="!loading && !error && !items.length"
          class="case-inbox__empty mq-soft"
        >
          <MqIconTile
            name="task"
            :size="44"
          /><strong>暂无病历沟通</strong>
        </div>
      </a-spin>
      <a-pagination
        v-if="total && !error"
        v-model:current="page"
        :total="total"
        :page-size="20"
        :show-size-changer="false"
        @change="load(false)"
      />
    </section>
    <a-drawer
      :open="detailOpen"
      width="min(620px, 100vw)"
      :root-style="{ zIndex: 1300 }"
      @close="close"
    >
      <template #title>
        <div class="case-detail__heading">
          <MqIconTile
            name="task"
            tone="brand"
            :size="36"
          />
          <div>
            <span>质控作业 · 消息详情</span>
            <h2>病历沟通</h2>
          </div>
        </div>
      </template>
      <section
        class="case-detail"
        aria-label="病历沟通详情"
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
        <a-spin
          :spinning="detailLoading"
          tip="正在核对消息来源"
        >
          <template v-if="selected">
            <div class="case-detail__object mq-soft">
              <div class="case-detail__object-head">
                <MqIconTile
                  :name="selected.scene === 'running' ? 'running' : 'final'"
                  :size="40"
                  tone="brand"
                />
                <div class="case-detail__object-copy">
                  <span>沟通病历</span>
                  <h3>{{ selected.visit_id }}</h3>
                </div>
                <span
                  class="mq-status"
                  :class="communicationStatusClass(selected)"
                >{{
                  selected.withdrawn ? '原催办已撤回' : communicationStatus(selected)
                }}</span>
              </div>
              <div class="case-detail__meta">
                <span>{{ selected.scene === 'running' ? '运行病历' : '终末病历' }}</span><span>{{ selected.department }}</span><span>规则版本 {{ selected.rule_set_version }}</span>
              </div>
              <details class="case-detail__source">
                <summary>保存结果来源</summary>
                <dl>
                  <div>
                    <dt>机构</dt>
                    <dd>{{ selected.institute_id }}</dd>
                  </div>
                  <div>
                    <dt>患者</dt>
                    <dd>{{ selected.patient_id }}</dd>
                  </div>
                  <div>
                    <dt>就诊</dt>
                    <dd>{{ selected.visit_id }}</dd>
                  </div>
                  <div>
                    <dt>冻结结果</dt>
                    <dd>{{ selected.root_job_id }} / {{ selected.envelope_id }}</dd>
                  </div>
                  <div>
                    <dt>规则集</dt>
                    <dd>{{ selected.rule_set_key }} · {{ selected.rule_set_version }}</dd>
                  </div>
                </dl>
              </details>
            </div>
            <section class="case-detail__body">
              <h3>{{ labels[selected.action] }}</h3>
              <p class="case-inbox__content">
                {{ selected.content }}
              </p>
            </section>
            <section class="case-detail__history">
              <div class="case-inbox__section-head">
                <h3>
                  <MqIcon
                    name="history"
                    :size="18"
                  />操作历史
                </h3>
                <span>{{ selected.history.length }} 条 · 北京时间</span>
              </div>
              <CaseCommunicationHistory
                class="case-inbox__history"
                :items="selected.history"
                :active-id="selected.id"
              />
            </section>
          </template>
        </a-spin>
      </section>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import CaseCommunicationHistory from '@/components/qc/CaseCommunicationHistory.vue'
import {
  communicationLabels as labels,
  communicationIcon,
  communicationStatus,
  communicationStatusClass,
  formatCommunicationTime as formatTime,
} from '@/components/qc/caseCommunicationPresentation'
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

<style scoped src="./styles/case-communications.css"></style>
