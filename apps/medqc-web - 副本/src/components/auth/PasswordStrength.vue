<template>
  <div
    v-if="password"
    class="password-strength"
  >
    <div class="mb-2">
      <div class="flex items-center justify-between text-xs">
        <span class="text-slate-400">密码强度</span>
        <span :class="strengthTextClass">{{ strengthText }}</span>
      </div>
      <div class="flex gap-1 mt-1">
        <div
          v-for="i in 4"
          :key="i"
          class="h-1 flex-1 rounded-full transition-colors duration-300"
          :class="i <= strengthLevel ? strengthColorClass : 'bg-slate-600'"
        />
      </div>
    </div>

    <!-- 密码要求检查 -->
    <div class="space-y-1">
      <div
        v-for="requirement in requirements"
        :key="requirement.key"
        class="flex items-center gap-2 text-xs"
      >
        <div
          class="w-3 h-3 rounded-full flex items-center justify-center"
          :class="requirement.met ? 'bg-emerald-500' : 'bg-slate-600'"
        >
          <CheckOutlined
            v-if="requirement.met"
            class="text-white text-[8px]"
          />
        </div>
        <span :class="requirement.met ? 'text-emerald-400' : 'text-slate-400'">
          {{ requirement.text }}
        </span>
      </div>
    </div>

    <!-- 安全提示 -->
    <div
      v-if="showTips && strengthLevel < 3"
      class="mt-3 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20"
    >
      <div class="flex items-start gap-2">
        <WarningOutlined class="text-amber-400 text-xs mt-0.5" />
        <div class="text-xs text-amber-300">
          <div class="font-medium mb-1">
            密码安全建议：
          </div>
          <ul class="space-y-0.5 text-amber-200/80">
            <li v-if="!hasMinLength">
              • 至少包含8个字符
            </li>
            <li v-if="!hasUppercase">
              • 包含大写字母
            </li>
            <li v-if="!hasLowercase">
              • 包含小写字母
            </li>
            <li v-if="!hasNumbers">
              • 包含数字
            </li>
            <li v-if="!hasSymbols">
              • 包含特殊符号
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckOutlined, WarningOutlined } from '@ant-design/icons-vue'

const passwordSymbolPattern = new RegExp('[!@#$%^&*()_+=[\\]{};:\'"\\\\|,.<>/?-]')

interface Props {
  password: string
  showTips?: boolean
  minLength?: number
}

const props = withDefaults(defineProps<Props>(), {
  showTips: true,
  minLength: 8,
})

// 密码强度检查
const hasMinLength = computed(() => props.password.length >= props.minLength)
const hasUppercase = computed(() => /[A-Z]/.test(props.password))
const hasLowercase = computed(() => /[a-z]/.test(props.password))
const hasNumbers = computed(() => /\d/.test(props.password))
const hasSymbols = computed(() => passwordSymbolPattern.test(props.password))

// 密码要求列表
const requirements = computed(() => [
  {
    key: 'length',
    text: `至少${props.minLength}个字符`,
    met: hasMinLength.value,
  },
  {
    key: 'uppercase',
    text: '包含大写字母',
    met: hasUppercase.value,
  },
  {
    key: 'lowercase',
    text: '包含小写字母',
    met: hasLowercase.value,
  },
  {
    key: 'numbers',
    text: '包含数字',
    met: hasNumbers.value,
  },
  {
    key: 'symbols',
    text: '包含特殊符号',
    met: hasSymbols.value,
  },
])

// 计算密码强度等级 (1-4)
const strengthLevel = computed(() => {
  let score = 0

  if (hasMinLength.value) score++
  if (hasUppercase.value) score++
  if (hasLowercase.value) score++
  if (hasNumbers.value) score++
  if (hasSymbols.value) score++

  // 额外加分项
  if (props.password.length >= 12) score += 0.5
  if (props.password.length >= 16) score += 0.5

  // 转换为1-4等级
  if (score >= 4.5) return 4
  if (score >= 3.5) return 3
  if (score >= 2) return 2
  return 1
})

// 强度文本
const strengthText = computed(() => {
  switch (strengthLevel.value) {
    case 4:
      return '很强'
    case 3:
      return '强'
    case 2:
      return '中等'
    default:
      return '弱'
  }
})

// 强度文本颜色
const strengthTextClass = computed(() => {
  switch (strengthLevel.value) {
    case 4:
      return 'text-emerald-400 font-medium'
    case 3:
      return 'text-blue-400 font-medium'
    case 2:
      return 'text-amber-400 font-medium'
    default:
      return 'text-red-400 font-medium'
  }
})

// 强度条颜色
const strengthColorClass = computed(() => {
  switch (strengthLevel.value) {
    case 4:
      return 'bg-emerald-500'
    case 3:
      return 'bg-blue-500'
    case 2:
      return 'bg-amber-500'
    default:
      return 'bg-red-500'
  }
})

// 密码强度评分 (0-100)
const strengthScore = computed(() => {
  return Math.min(100, (strengthLevel.value / 4) * 100)
})

// 是否为强密码
const isStrongPassword = computed(() => strengthLevel.value >= 3)

// 暴露给父组件的属性和方法
defineExpose({
  strengthLevel,
  strengthScore,
  isStrongPassword,
  requirements: requirements.value,
})
</script>

<style scoped>
.password-strength {
  @apply text-sm;
}

/* 动画效果 */
.password-strength > * {
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 强度条动画 */
.h-1 {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 要求检查项动画 */
.space-y-1 > div {
  transition: all 0.2s ease-out;
}

.space-y-1 > div:hover {
  transform: translateX(2px);
}
</style>
