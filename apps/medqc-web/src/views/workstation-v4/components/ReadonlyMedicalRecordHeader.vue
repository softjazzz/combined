<template>
  <header class="readonly-medical-record-header">
    <div class="readonly-medical-record-header__title">
      <FileText :size="18" aria-hidden="true" />
      <h2>查看病历</h2>
      <span>只读</span>
    </div>
    <MedicalRecordContextBanner :context="context" />
  </header>
</template>

<script setup lang="ts">
import { FileText } from 'lucide-vue-next'
import MedicalRecordContextBanner, {
  type MedicalRecordBannerContext,
} from '../customer-sample-validation/MedicalRecordContextBanner.vue'

defineProps<{ context: MedicalRecordBannerContext | null }>()
</script>

<style scoped>
.readonly-medical-record-header {
  display: flex;
  flex-wrap: wrap;
  flex-shrink: 0;
  align-items: center;
  gap: 8px 16px;
  min-width: 0;
}

.readonly-medical-record-header__title {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
}

.readonly-medical-record-header__title svg {
  color: var(--mq-brand-600);
}

.readonly-medical-record-header__title h2 {
  margin: 0;
  color: var(--mq-text-primary);
  font-size: 17px;
  font-weight: 700;
}

.readonly-medical-record-header__title > span {
  color: var(--mq-text-tertiary);
  font-size: 12px;
}
</style>
