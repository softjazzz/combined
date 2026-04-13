<template>
  <div class="min-h-[400px] px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5">
    <div
      class="mx-auto w-full max-w-[1200px] rounded-[18px] border border-slate-200/55 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(250,252,255,0.98))] p-2.5 shadow-[0_8px_20px_rgba(15,23,42,0.03)]"
    >
      <div
        v-if="settlementLoading"
        class="flex flex-col items-center py-20"
      >
        <a-spin size="large" />
        <div class="text-sm text-slate-400 mt-4">
          加载结算清单...
        </div>
      </div>
      <div v-else-if="settlementData">
        <div
          v-if="settlementData?.data_source === 'generated_from_frontpage'"
          class="mx-1 mb-3 flex items-center gap-3 rounded-[14px] border border-blue-100/80 bg-[linear-gradient(180deg,rgba(244,248,255,0.94),rgba(255,255,255,0.98))] px-4 py-3"
        >
          <span class="text-base text-blue-500">☑</span>
          <div class="min-w-0">
            <div class="text-sm font-semibold text-blue-700">
              AI 生成草稿
            </div>
            <div class="text-xs text-slate-500">
              本清单由病案首页 AI 抽取结果和 CDM 数据自动组装，需人工审核后方可上传医保系统。
            </div>
          </div>
          <a-tag
            color="blue"
            class="ml-auto flex-shrink-0 !rounded-full"
          >
            Draft
          </a-tag>
        </div>
        <div
          class="mb-4 flex items-center justify-between rounded-[14px] border border-slate-200/80 bg-white/72 px-4 py-3"
        >
          <div class="text-[13px] text-slate-500">
            清单流水号
            <span class="font-mono font-bold text-slate-700">{{
              settlementData.medinsur_serial_no || '-'
            }}</span>
          </div>
          <div class="flex items-center gap-2">
            <a-button
              size="small"
              class="!rounded-full !border-slate-200/80 !shadow-none"
              :loading="settlementQcLoading"
              @click="emit('run-settlement-qc')"
            >
              <template #icon>
                <CheckOutlined />
              </template>
              执行质控
            </a-button>
          </div>
        </div>

        <SettlementSheet :data="settlementData" />

        <div
          v-if="settlementQcReport"
          class="mb-6"
        >
          <h4
            class="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400"
          >
            <CheckCircleOutlined class="text-blue-500" /> 质控结果
          </h4>
          <div class="mb-4 grid grid-cols-4 gap-2.5">
            <div class="rounded-[14px] border border-blue-100/80 bg-blue-50/70 p-3 text-center">
              <div class="text-2xl font-black text-blue-600">
                {{ settlementQcReport.summary.total }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">
                总规则数
              </div>
            </div>
            <div class="rounded-[14px] border border-slate-200/80 bg-slate-50/88 p-3 text-center">
              <div class="text-2xl font-black text-slate-700">
                {{ settlementQcReport.summary.passed }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">
                通过
              </div>
            </div>
            <div class="rounded-[14px] border border-blue-100/80 bg-blue-50/50 p-3 text-center">
              <div class="text-2xl font-black text-blue-700">
                {{ settlementQcReport.summary.failed }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">
                未通过
              </div>
            </div>
            <div class="rounded-[14px] border border-slate-200/80 bg-white/88 p-3 text-center">
              <div class="text-2xl font-black text-slate-700">
                {{ settlementQcReport.summary.pass_rate }}
              </div>
              <div class="text-[10px] text-slate-400 mt-1">
                通过率
              </div>
            </div>
          </div>
          <div class="space-y-2">
            <div
              v-for="r in settlementQcReport.results.filter((x: any) => !x.passed)"
              :key="r.rule_id"
              class="flex items-start gap-3 rounded-[14px] border bg-white/88 px-4 py-3 dark:bg-slate-800"
              :class="
                r.severity === 'error' ? 'border-blue-200 bg-blue-50/35' : 'border-slate-200/80'
              "
            >
              <a-tag
                color="blue"
                class="mt-0.5 flex-shrink-0"
              >
                {{ r.rule_id }}
              </a-tag>
              <div class="min-w-0">
                <div class="text-sm font-medium text-slate-800 dark:text-slate-200">
                  {{ r.field_name }}
                </div>
                <div class="text-xs text-slate-500 mt-0.5">
                  {{ r.message }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        v-else
        class="flex min-h-[360px] flex-col items-center justify-center rounded-[16px] border border-dashed border-blue-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(245,249,255,0.98))] px-6 py-12 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_rgba(148,163,184,0.08)]"
      >
        <div
          class="mb-4 flex h-16 w-16 items-center justify-center rounded-[20px] border border-blue-200/80 bg-[linear-gradient(180deg,#eef4ff,#dbeafe)] shadow-[0_12px_24px_rgba(59,130,246,0.14),inset_0_1px_0_rgba(255,255,255,0.8)]"
        >
          <MedicineBoxOutlined class="text-[28px] text-blue-600" />
        </div>
        <div class="text-[18px] font-black text-slate-900">
          暂无结算清单数据
        </div>
        <div class="mt-2 max-w-[360px] text-[13px] leading-6 text-slate-500">
          当前病历还没有正式结算清单，可根据首页草稿和 CDM 数据生成一份结算草稿后继续质控。
        </div>
        <div class="mt-6 flex items-center gap-2">
          <a-button
            type="primary"
            class="!h-10 !rounded-full !border-0 !px-5 !text-sm !font-bold !shadow-[0_10px_20px_rgba(37,99,235,0.18)]"
            :disabled="
              !canGenerateSettlement || !selectedRecord?.patientId || !selectedRecord?.visitId
            "
            @click="emit('generate-settlement-draft')"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            生成结算草稿
          </a-button>
          <a-button
            class="!h-10 !rounded-full !border-slate-200/90 !bg-white/85 !px-5 !text-sm !font-semibold !text-slate-600"
            @click="emit('reload-settlement')"
          >
            <template #icon>
              <SyncOutlined />
            </template>
            重新加载
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  CheckCircleOutlined,
  CheckOutlined,
  MedicineBoxOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import SettlementSheet from './SettlementSheet.vue'
import type { PatientRecord } from '../types'

interface SettlementQcRuleResult {
  rule_id: string
  passed: boolean
  severity: string
  field_name: string
  message: string
}

interface SettlementQcReport {
  summary: {
    total: number
    passed: number
    failed: number
    pass_rate: string
  }
  results: SettlementQcRuleResult[]
}

defineProps<{
  settlementLoading: boolean
  settlementData: Record<string, any> | null
  settlementQcLoading: boolean
  settlementQcReport: SettlementQcReport | null
  canGenerateSettlement: boolean
  selectedRecord: PatientRecord | null
}>()

const emit = defineEmits<{
  'run-settlement-qc': []
  'generate-settlement-draft': []
  'reload-settlement': []
}>()
</script>
