<template>
  <div class="hospital-loading" :class="{ 'is-compact': compact }" role="status">
    <div class="hospital-loading__mark">
      <div class="hospital-loading__logo">
        <img :src="hospitalLogo" alt="泸县人民医院" width="270" height="68" />
      </div>
    </div>
    <p class="hospital-loading__status">{{ label }}</p>
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
  gap: 14px;
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

.hospital-loading__status {
  margin: 0;
  color: #165368;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.5;
  letter-spacing: 0.08em;
}

@supports (background-clip: text) {
  @media (prefers-reduced-motion: no-preference) and (forced-colors: none) {
    .hospital-loading__status {
      background: linear-gradient(105deg, #165368 38%, #147783 50%, #165368 62%) 100% 50% / 240% 100%;
      background-clip: text;
      color: transparent;
      animation: hospital-status-shine 2.35s ease-in-out infinite;
    }
  }
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

.is-compact .hospital-loading__status {
  font-size: 16px;
}

@keyframes hospital-status-shine {
  from {
    background-position: 100% 50%;
  }

  84%,
  to {
    background-position: 0% 50%;
  }
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
