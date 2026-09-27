<template>
  <section class="customer-sample-luxian-scope">
    <div class="customer-sample-luxian-scope-head">
      <div>
        <div class="customer-sample-luxian-scope-title">
          泸县0609质控点范围
        </div>
        <p>{{ helperText }}</p>
      </div>
      <div class="customer-sample-luxian-scope-actions">
        <span>{{ modeText }}</span>
        <a-button
          size="small"
          class="!rounded-lg"
          @click="emit('select-all')"
        >
          {{ allRulesSelected ? '取消全部勾选' : `全选${families.length}个质控族` }}
        </a-button>
        <a-button
          v-if="selectedRuleIds.length && !allRulesSelected"
          size="small"
          class="!rounded-lg"
          @click="emit('clear')"
        >
          清空勾选
        </a-button>
      </div>
    </div>
    <div class="customer-sample-luxian-scope-overview">
      <span>
        <strong>{{ families.length }}</strong>
        个质控族
      </span>
      <span>
        <strong>{{ allRuleIds.length }}</strong>
        个质控点
      </span>
      <span>
        <strong>{{ selectedFamilyCount }}</strong>
        个质控族已选
      </span>
      <span>
        <strong>{{ selectedRuleIds.length || families.flatMap((family) => family.rules).filter((rule) => rule.releaseScope !== 'acceptance_only').length }}</strong>
        个质控点将运行
      </span>
    </div>
    <div class="customer-sample-luxian-rule-groups">
      <div
        v-for="family in families"
        :key="family.key"
        class="customer-sample-luxian-rule-group"
        :class="{
          'is-selected': familySelectedCount(family) > 0,
          'is-expanded': isFamilyExpanded(family.key),
        }"
      >
        <div class="customer-sample-luxian-rule-group-head">
          <div class="customer-sample-luxian-rule-group-main">
            <div class="customer-sample-luxian-family-icon">
              <component :is="resolveFamilyIcon(family.key)" />
            </div>
            <div class="customer-sample-luxian-rule-group-copy">
              <div class="customer-sample-luxian-rule-group-title">
                <strong>{{ family.name }}</strong>
                <span>{{ family.rules.length }} 条</span>
                <em v-if="familySelectedCount(family) > 0">
                  已选 {{ familySelectedCount(family) }}/{{ family.rules.length }}
                </em>
              </div>
              <small>{{ family.description }}</small>
            </div>
          </div>
          <div class="customer-sample-luxian-rule-group-actions">
            <button
              type="button"
              :class="{ 'is-selected-action': isFamilySelected(family.ruleIds) }"
              @click="emit('toggle-family', family.ruleIds)"
            >
              {{ isFamilySelected(family.ruleIds) ? '取消本组' : '选择本组' }}
            </button>
            <button
              type="button"
              class="is-ghost"
              @click="emit('toggle-expanded', family.key)"
            >
              {{ isFamilyExpanded(family.key) ? '收起明细' : '查看质控点' }}
            </button>
          </div>
        </div>
        <div
          v-if="isFamilyExpanded(family.key)"
          class="customer-sample-luxian-rule-options"
        >
          <label
            v-for="rule in family.rules"
            :key="rule.ruleId"
            class="customer-sample-luxian-rule-option"
            :class="{ 'is-selected': selectedRuleSet.has(rule.ruleId) }"
            :title="`${rule.ruleId} ${rule.name}`"
          >
            <input
              type="checkbox"
              class="luxian-rule-checkbox"
              :value="rule.ruleId"
              :checked="selectedRuleSet.has(rule.ruleId)"
              @change="emit('toggle-rule', rule.ruleId)"
            >
            <span>{{ rule.ruleId }}</span>
            <em>{{ rule.name }}<small v-if="rule.releaseScope === 'acceptance_only'"> · 待验收</small></em>
          </label>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Clock3,
  Droplets,
  FlaskConical,
  MessagesSquare,
  Microscope,
  Scissors,
  Stethoscope,
} from 'lucide-vue-next'

type LuxianRuleOption = {
  ruleId: string
  releaseScope?: 'default' | 'acceptance_only'
  name: string
  description: string
  requiredDocumentsLabel: string
}

type LuxianRuleFamily = {
  key: string
  name: string
  description: string
  rules: LuxianRuleOption[]
  ruleIds: string[]
}

const props = defineProps<{
  families: LuxianRuleFamily[]
  selectedRuleIds: string[]
  expandedFamilyKeys: string[]
  helperText: string
  modeText: string
  allRuleIds: string[]
  selectedFamilyCount: number
  allRulesSelected: boolean
}>()

const emit = defineEmits<{
  'select-all': []
  clear: []
  'toggle-family': [ruleIds: string[]]
  'toggle-expanded': [familyKey: string]
  'toggle-rule': [ruleId: string]
}>()

const selectedRuleSet = computed(() => new Set(props.selectedRuleIds))

const LUXIAN_RULE_FAMILY_ICONS = {
  basic_timeliness: Clock3,
  course_quality: Stethoscope,
  exam_lab: Microscope,
  consultation_quality: MessagesSquare,
  surgery_anesthesia: Scissors,
  transfusion: Droplets,
  tumor_pathology: FlaskConical,
} as const

function familySelectedCount(family: LuxianRuleFamily): number {
  return family.ruleIds.filter((ruleId) => selectedRuleSet.value.has(ruleId)).length
}

function isFamilySelected(ruleIds: string[]): boolean {
  const acceptanceOnly = new Set(props.families.flatMap((family) => family.rules)
    .filter((rule) => rule.releaseScope === 'acceptance_only').map((rule) => rule.ruleId))
  const defaultIds = ruleIds.filter((id) => !acceptanceOnly.has(id))
  return defaultIds.length > 0 && defaultIds.every((ruleId) => selectedRuleSet.value.has(ruleId))
}

function isFamilyExpanded(familyKey: string): boolean {
  return props.expandedFamilyKeys.includes(familyKey)
}

function resolveFamilyIcon(familyKey: string) {
  return LUXIAN_RULE_FAMILY_ICONS[familyKey as keyof typeof LUXIAN_RULE_FAMILY_ICONS] || Stethoscope
}
</script>

<style scoped>
.customer-sample-luxian-scope {
  margin-top: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  padding: 12px 14px 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.035);
}

.customer-sample-luxian-scope-head,
.customer-sample-luxian-rule-group-head,
.customer-sample-luxian-scope-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.customer-sample-luxian-scope-head,
.customer-sample-luxian-rule-group-head {
  justify-content: space-between;
}

.customer-sample-luxian-scope-head {
  gap: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding-bottom: 10px;
}

.customer-sample-luxian-scope-title {
  color: var(--customer-sample-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
}

.customer-sample-luxian-scope p,
.customer-sample-luxian-rule-group-head small {
  margin: 2px 0 0;
  color: var(--customer-sample-muted);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-luxian-scope-actions span {
  white-space: nowrap;
  border: 1px solid rgba(0, 102, 204, 0.12);
  border-radius: 999px;
  background: rgba(234, 242, 255, 0.72);
  padding: 4px 10px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.customer-sample-luxian-scope-overview {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.customer-sample-luxian-scope-overview span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.82);
  padding: 4px 9px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-sample-luxian-scope-overview strong {
  color: var(--customer-sample-primary);
  font-weight: 750;
}

.customer-sample-luxian-rule-groups {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.065);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
}

.customer-sample-luxian-rule-group {
  min-width: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.055);
  background: rgba(255, 255, 255, 0.54);
  padding: 9px 10px;
  transition:
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-luxian-rule-group:last-child {
  border-bottom: 0;
}

.customer-sample-luxian-rule-group.is-selected {
  background: rgba(234, 242, 255, 0.44);
}

.customer-sample-luxian-rule-group.is-expanded {
  background: rgba(248, 250, 252, 0.8);
}

.customer-sample-luxian-rule-group-head {
  min-height: 42px;
  gap: 12px;
}

.customer-sample-luxian-rule-group-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.customer-sample-luxian-family-icon {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 102, 204, 0.1);
  border-radius: 10px;
  background: rgba(234, 242, 255, 0.72);
  color: var(--customer-sample-primary);
}

.customer-sample-luxian-family-icon svg {
  width: 16px;
  height: 16px;
  stroke-width: 2.1;
}

.customer-sample-luxian-rule-group-copy {
  min-width: 0;
}

.customer-sample-luxian-rule-group-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.customer-sample-luxian-rule-group-head strong {
  color: var(--customer-sample-text);
  font-size: 13px;
  font-weight: 700;
  line-height: 19px;
}

.customer-sample-luxian-rule-group-title span {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  padding: 2px 7px;
  color: var(--customer-sample-primary);
  font-size: 11px;
  font-weight: 750;
  line-height: 16px;
}

.customer-sample-luxian-rule-group-title em {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.08);
  padding: 2px 7px;
  color: #047857;
  font-size: 11px;
  font-style: normal;
  font-weight: 750;
  line-height: 16px;
}

.customer-sample-luxian-rule-group-head small {
  display: block;
  overflow: hidden;
  max-width: 100%;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-sample-luxian-rule-group-actions {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.customer-sample-luxian-rule-group-actions button {
  flex: 0 0 auto;
  border: 0;
  border-radius: 8px;
  background: rgba(0, 102, 204, 0.07);
  padding: 4px 8px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  cursor: pointer;
  transition:
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-luxian-rule-group-actions button:hover {
  background: rgba(0, 102, 204, 0.12);
}

.customer-sample-luxian-rule-group-actions button.is-selected-action {
  background: rgba(245, 158, 11, 0.11);
  color: #b45309;
}

.customer-sample-luxian-rule-group-actions button.is-selected-action:hover {
  background: rgba(245, 158, 11, 0.17);
  color: #92400e;
}

.customer-sample-luxian-rule-group-actions button.is-ghost {
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.62);
}

.customer-sample-luxian-rule-group-actions button.is-ghost:hover {
  background: rgba(0, 102, 204, 0.08);
  color: var(--customer-sample-primary);
}

.customer-sample-luxian-rule-options {
  margin-top: 9px;
  margin-left: 42px;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.customer-sample-luxian-rule-option {
  min-width: 0;
  max-width: 100%;
  display: inline-grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.8);
  padding: 5px 9px;
  color: var(--customer-sample-muted);
  transition:
    border-color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-luxian-rule-option.is-selected {
  border-color: rgba(0, 102, 204, 0.26);
  background: rgba(234, 242, 255, 0.9);
  color: var(--customer-sample-primary);
  box-shadow: 0 1px 3px rgba(0, 102, 204, 0.08);
}

.customer-sample-luxian-rule-option input {
  width: 14px;
  height: 14px;
  margin: 0;
}

.customer-sample-luxian-rule-option span {
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.customer-sample-luxian-rule-option em {
  overflow: hidden;
  max-width: 260px;
  color: var(--customer-sample-text);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-style: normal;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

@media (max-width: 900px) {
  .customer-sample-luxian-scope-head,
  .customer-sample-luxian-scope-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .customer-sample-luxian-rule-group-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .customer-sample-luxian-rule-group-actions {
    width: 100%;
  }

  .customer-sample-luxian-rule-options {
    margin-left: 0;
  }
}
</style>
