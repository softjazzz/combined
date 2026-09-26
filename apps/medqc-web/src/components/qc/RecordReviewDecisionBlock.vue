<template>
  <section
    class="record-review"
    aria-label="病历审核"
  >
    <div class="record-review__heading">
      <div class="record-review__title">
        <h4>病历审核</h4>
        <a-tag
          v-if="controller.view"
          :color="reviewStateColor(controller.view.state)"
          data-testid="record-review-state"
        >
          {{ reviewStateLabel(controller.view.state) }}
        </a-tag>
      </div>
      <a-button
        size="small"
        :loading="controller.loading"
        :disabled="controller.submitting"
        data-testid="record-review-refresh"
        @click="void controller.refresh()"
      >
        <RotateCw
          :size="14"
          aria-hidden="true"
        />刷新
      </a-button>
    </div>

    <p
      v-if="controller.loading && !controller.view"
      class="record-review__muted"
    >
      正在读取审核状态…
    </p>
    <p
      v-else-if="controller.loadError && !controller.view"
      class="record-review__error"
      role="alert"
    >
      {{ controller.loadError }}
    </p>
    <template v-else-if="controller.view">
      <p
        v-if="controller.view.state === 'unavailable'"
        class="record-review__muted"
        data-testid="record-review-unavailable"
      >
        不可审核：{{ reviewUnavailableReason(controller.view.reason_code) }}
      </p>
      <p
        v-else-if="controller.view.current"
        class="record-review__muted"
      >
        {{ reviewStageLabel(controller.view.current.stage) }}结论：{{ reviewDecisionLabel(controller.view.current.decision) }}（决定不可修改，如需推翻请重新质控）
      </p>
      <p
        v-else-if="controller.view.state === 'pending_recheck'"
        class="record-review__muted"
      >
        上一次结果审核存疑，本次重质控结果待复审。
      </p>

      <div
        v-if="isPendingReviewState(controller.view.state)"
        class="record-review__actions"
      >
        <a-button
          type="primary"
          :disabled="!controller.canAct"
          :loading="controller.submitting && controller.activeDecision === 'approved'"
          data-testid="record-review-approve"
          @click="controller.openDecision('approved')"
        >
          审核通过
        </a-button>
        <a-button
          danger
          :disabled="!controller.canAct"
          :loading="controller.submitting && controller.activeDecision === 'doubtful'"
          data-testid="record-review-doubt"
          @click="controller.openDecision('doubtful')"
        >
          审核存疑
        </a-button>
      </div>
      <p
        v-if="isPendingReviewState(controller.view.state) && !controller.view.can_submit"
        class="record-review__muted"
      >
        {{ blockedMessage }}
      </p>
    </template>

    <p
      v-if="controller.actionError"
      class="record-review__error"
      role="alert"
      data-testid="record-review-error"
    >
      {{ controller.actionError }}
    </p>
    <p
      v-if="controller.successMessage"
      class="record-review__success"
      role="status"
    >
      {{ controller.successMessage }}
    </p>

    <div
      v-if="controller.view && controller.view.history.length"
      class="record-review__history"
    >
      <h5>审核历史</h5>
      <ul>
        <li
          v-for="entry in controller.view.history"
          :key="entry.id"
          data-testid="record-review-history-item"
        >
          <div class="record-review__history-heading">
            <span>{{ formatReviewTime(entry.created_at) }}</span>
            <span>{{ reviewStageLabel(entry.stage) }}</span>
            <a-tag :color="entry.decision === 'approved' ? 'success' : 'warning'">
              {{ reviewDecisionLabel(entry.decision) }}
            </a-tag>
            <span>审核人 {{ entry.reviewer_id || '未知' }}</span>
            <slot
              name="history-meta"
              :entry="entry"
            />
          </div>
          <p v-if="entry.reason">
            原因：{{ entry.reason }}
          </p>
        </li>
      </ul>
    </div>

    <a-modal
      :open="controller.decisionOpen"
      :title="controller.activeDecision === 'doubtful' ? '审核存疑' : '审核通过'"
      :confirm-loading="controller.submitting"
      ok-text="提交"
      cancel-text="取消"
      @ok="void controller.confirmDecision()"
      @cancel="controller.closeDecision()"
    >
      <p class="record-review__muted">
        审核决定提交后不可修改。
      </p>
      <label for="record-review-reason">{{ controller.activeDecision === 'doubtful' ? '存疑原因（必填）' : '备注（可选）' }}</label>
      <a-textarea
        id="record-review-reason"
        :value="controller.reason"
        :maxlength="2000"
        :rows="3"
        :disabled="controller.submitting"
        @update:value="controller.setReason"
      />
      <p
        v-if="controller.reasonError"
        class="record-review__error"
        role="alert"
      >
        {{ controller.reasonError }}
      </p>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
/**
 * 病历审核的上下文无关展示：状态标签、不可审核原因、通过/存疑按钮与弹窗、审核历史。
 * 交互状态由 useRecordReviewDecision 提供，任务/病例面板只负责注入上下文适配器。
 */
import { RotateCw } from 'lucide-vue-next'
import {
  formatReviewTime,
  isPendingReviewState,
  reviewDecisionLabel,
  reviewStageLabel,
  reviewStateColor,
  reviewStateLabel,
  reviewUnavailableReason,
} from '@/composables/useRecordReviewDecision'
import type { RecordReviewDecisionController } from '@/composables/useRecordReviewDecision'

defineProps<{
  controller: RecordReviewDecisionController
  /** 待审核但服务端不允许提交时的说明（随上下文不同）。 */
  blockedMessage: string
}>()
</script>

<style scoped>
.record-review { margin-top: 18px; padding-top: 16px; border-top: 1px solid rgba(0, 0, 0, .08); }
.record-review__heading, .record-review__title, .record-review__actions, .record-review__history-heading { display: flex; align-items: center; gap: 10px; }
.record-review__heading { justify-content: space-between; }
.record-review__heading h4, .record-review__history h5 { margin: 0; font-size: 14px; font-weight: 600; }
.record-review__heading button { display: inline-flex; align-items: center; gap: 5px; }
.record-review__actions { margin-top: 10px; }
.record-review__muted { margin: 8px 0 0; color: rgba(29, 29, 31, .6); font-size: 13px; }
.record-review__error { margin: 8px 0 0; color: #b42318; }
.record-review__success { margin: 8px 0 0; color: #067647; }
.record-review__history { margin-top: 14px; }
.record-review__history ul { margin: 8px 0 0; padding: 0; list-style: none; }
.record-review__history li { padding: 10px 0; border-bottom: 1px solid rgba(0, 0, 0, .06); }
.record-review__history-heading { flex-wrap: wrap; color: rgba(29, 29, 31, .7); font-size: 13px; }
.record-review__history li p { margin: 6px 0 0; line-height: 22px; overflow-wrap: anywhere; }
</style>
