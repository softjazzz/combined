<template>
  <div class="hospital-loading" :class="{ 'is-compact': compact, 'fills-reading-area': fill }" role="status">
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
  fill?: boolean
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
  position: relative;
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

@media (prefers-reduced-motion: no-preference) and (forced-colors: none) {
  .hospital-loading__mark::after {
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-radius: inherit;
    box-shadow: 0 0 0 1px rgba(36, 154, 230, 0.22), 0 0 20px rgba(24, 156, 225, 0.34);
    animation: hospital-logo-glow 1.8s ease-in-out infinite;
    content: '';
  }

  @supports (mask-image: none) {
    .hospital-loading__logo::after {
      position: absolute;
      inset: 0;
      pointer-events: none;
      mask: url('@/assets/images/lx-logo.png') center / 100% 100% no-repeat;
      background: linear-gradient(
        112deg,
        transparent 34%,
        rgba(0, 156, 229, 0.72) 43%,
        #b4f3ff 48%,
        #fff 50%,
        #b4f3ff 52%,
        rgba(52, 147, 255, 0.76) 57%,
        transparent 66%
      ) 96% 50% / 240% 100% no-repeat;
      animation: hospital-logo-shine 1.8s ease-out infinite;
      content: '';
    }
  }
}

.hospital-loading__status {
  max-inline-size: 100%;
  margin: 0;
  color: #165368;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: 0.04em;
  overflow-wrap: anywhere;
}

.hospital-loading.fills-reading-area {
  flex: 1 1 0;
  inline-size: 100%;
  block-size: 100%;
  min-block-size: 0;
  grid-template-rows: minmax(0, 1fr) auto minmax(0, 1fr);
  align-content: stretch;
  gap: 0;
}

.fills-reading-area .hospital-loading__mark {
  grid-row: 2;
}

.fills-reading-area .hospital-loading__status {
  grid-row: 3;
  align-self: start;
  margin-block-start: 14px;
}

@supports (background-clip: text) {
  @media (prefers-reduced-motion: no-preference) and (forced-colors: none) {
    .hospital-loading__status {
      background: linear-gradient(105deg, #165368 33%, #00758f 43%, #096ad1 50%, #00758f 57%, #165368 67%)
        90% 50% / 240% 100% no-repeat;
      background-clip: text;
      color: transparent;
      animation: hospital-status-shine 1.8s ease-in-out infinite;
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

@keyframes hospital-status-shine {
  from {
    background-position: 90% 50%;
    transform: translateY(0);
  }

  36% {
    transform: translateY(-2px);
  }

  72%,
  to {
    background-position: 0% 50%;
    transform: translateY(0);
  }
}

@keyframes hospital-logo-shine {
  from {
    background-position: 96% 50%;
  }

  72%,
  to {
    background-position: 0% 50%;
  }
}

@keyframes hospital-logo-glow {
  from,
  to {
    opacity: 0.7;
  }

  35% {
    opacity: 1;
  }

  78% {
    opacity: 0.42;
  }
}
</style>
