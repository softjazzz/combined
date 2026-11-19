<template>
  <div class="hospital-loading" :class="{ 'is-compact': compact }" role="status">
    <div class="hospital-loading__mark">
      <div class="hospital-loading__logo">
        <img :src="hospitalLogo" alt="泸县人民医院" width="270" height="68" />
      </div>
    </div>
    <p>{{ label }}</p>
  </div>
</template>

<script setup lang="ts">
import hospitalLogo from '@/assets/images/lx-logo.png'

defineProps<{
  label: string
  compact?: boolean
}>()
</script>

<style scoped>
.hospital-loading {
  display: grid;
  box-sizing: border-box;
  min-block-size: 248px;
  justify-items: center;
  align-content: center;
  gap: 12px;
  padding: 24px 16px;
  text-align: center;
}

.hospital-loading__mark {
  box-sizing: border-box;
  max-inline-size: 100%;
  padding: 13px 18px;
  border: 1px solid var(--mq-info-border, #dce8f5);
  border-radius: 16px;
  background: var(--mq-bg-surface, #fff);
  box-shadow: 0 4px 16px rgba(20, 69, 96, 0.06);
}

.hospital-loading__logo {
  position: relative;
  inline-size: 162px;
  max-inline-size: 100%;
}

.hospital-loading__logo img {
  display: block;
  inline-size: 100%;
  block-size: auto;
}

@supports (mask-image: none) {
  .hospital-loading__logo::after {
    position: absolute;
    inset: 0;
    pointer-events: none;
    mask: url('@/assets/images/lx-logo.png') center / 100% 100% no-repeat;
    background: linear-gradient(
      112deg,
      transparent 40%,
      rgba(125, 220, 235, 0.45) 47%,
      rgba(255, 255, 255, 0.9) 50%,
      rgba(151, 203, 255, 0.52) 53%,
      transparent 60%
    ) 100% 50% / 260% 100% no-repeat;
    animation: hospital-logo-shine 2.35s ease-in-out infinite;
    content: '';
  }
}

.hospital-loading p {
  margin: 0;
  color: var(--mq-text-secondary, #515154);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.hospital-loading.is-compact {
  min-block-size: 0;
  gap: 8px;
  padding: 8px 0;
}

.is-compact .hospital-loading__mark {
  padding: 8px 10px;
  border-radius: 10px;
  box-shadow: none;
}

.is-compact .hospital-loading__logo {
  inline-size: 118px;
}

@keyframes hospital-logo-shine {
  from {
    background-position: 100% 50%;
  }

  84%,
  to {
    background-position: 0% 50%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hospital-loading__logo::after {
    content: none;
  }
}
</style>
