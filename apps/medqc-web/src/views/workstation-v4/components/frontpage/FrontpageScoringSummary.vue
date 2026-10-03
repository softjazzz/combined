<template>
  <section class="frontpage-scoring" aria-label="本次首页配置评分" data-testid="frontpage-current-scoring">
    <div><span>本次配置评分</span><strong>{{ scoring?.status === 'scored' ? scoring.score : scoring?.status === 'no_standard' ? '未配置评分标准' : scoring?.status === 'unavailable' ? '评分不可用' : '未知' }}</strong></div>
    <div><span>等级</span><strong>{{ scoring?.status === 'scored' ? scoring.grade ?? '未知' : '未知' }}</strong></div>
    <div><span>评分标准版本</span><strong>{{ scoring?.standard_id ?? '未知' }} / {{ scoring?.standard_version_seq ?? '未知' }}</strong></div>
  </section>
</template>
<script setup lang="ts">
import type { FrontpageFormalScore } from '@/api/scoring'
defineProps<{ scoring: FrontpageFormalScore | null }>()
</script>
<style scoped>
.frontpage-scoring { display: flex; flex-wrap: wrap; gap: 12px 24px; padding: 12px 0; border-bottom: 1px solid var(--border-color); }
.frontpage-scoring div { display: grid; gap: 4px; min-width: 100px; }
.frontpage-scoring span { color: var(--text-secondary); font-size: 12px; }
.frontpage-scoring strong { color: var(--text-primary); font-size: 14px; overflow-wrap: anywhere; }
</style>
