/**
 * 响应式断点工具
 * 提供屏幕尺寸检测和响应式布局支持
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'

// 断点定义
export const breakpoints = {
  xs: 480,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600
} as const

export type Breakpoint = keyof typeof breakpoints

// 响应式断点状态
const windowWidth = ref(0)

// 更新窗口宽度
const updateWidth = () => {
  windowWidth.value = window.innerWidth
}

// 全局监听器管理
let listenersCount = 0
let resizeListener: (() => void) | null = null

export function useBreakpoints() {
  // 计算当前断点
  const currentBreakpoint = computed<Breakpoint>(() => {
    const width = windowWidth.value
    if (width < breakpoints.xs) return 'xs'
    if (width < breakpoints.sm) return 'xs'
    if (width < breakpoints.md) return 'sm'
    if (width < breakpoints.lg) return 'md'
    if (width < breakpoints.xl) return 'lg'
    if (width < breakpoints.xxl) return 'xl'
    return 'xxl'
  })

  // 各种尺寸判断
  const isXs = computed(() => windowWidth.value < breakpoints.sm)
  const isSm = computed(() => windowWidth.value >= breakpoints.sm && windowWidth.value < breakpoints.md)
  const isMd = computed(() => windowWidth.value >= breakpoints.md && windowWidth.value < breakpoints.lg)
  const isLg = computed(() => windowWidth.value >= breakpoints.lg && windowWidth.value < breakpoints.xl)
  const isXl = computed(() => windowWidth.value >= breakpoints.xl && windowWidth.value < breakpoints.xxl)
  const isXxl = computed(() => windowWidth.value >= breakpoints.xxl)

  // 常用组合判断
  const isMobile = computed(() => windowWidth.value < breakpoints.md)
  const isTablet = computed(() => windowWidth.value >= breakpoints.md && windowWidth.value < breakpoints.lg)
  const isDesktop = computed(() => windowWidth.value >= breakpoints.lg)
  const isSmallScreen = computed(() => windowWidth.value < breakpoints.lg)
  const isLargeScreen = computed(() => windowWidth.value >= breakpoints.xl)

  // 断点匹配函数
  const matches = (breakpoint: Breakpoint | `${Breakpoint}+` | `${Breakpoint}-`) => {
    const width = windowWidth.value
    
    if (breakpoint.endsWith('+')) {
      // 大于等于指定断点
      const bp = breakpoint.slice(0, -1) as Breakpoint
      return width >= breakpoints[bp]
    } else if (breakpoint.endsWith('-')) {
      // 小于指定断点
      const bp = breakpoint.slice(0, -1) as Breakpoint
      return width < breakpoints[bp]
    } else {
      // 精确匹配断点范围
      const bp = breakpoint as Breakpoint
      const bpKeys = Object.keys(breakpoints) as Breakpoint[]
      const currentIndex = bpKeys.indexOf(bp)
      const nextBp = bpKeys[currentIndex + 1]
      
      if (nextBp) {
        return width >= breakpoints[bp] && width < breakpoints[nextBp]
      } else {
        return width >= breakpoints[bp]
      }
    }
  }

  // 响应式类名生成
  const getResponsiveClass = (baseClass: string, variants?: Partial<Record<Breakpoint, string>>) => {
    const classes = [baseClass]
    
    if (variants) {
      for (const [bp, className] of Object.entries(variants)) {
        if (matches(bp as Breakpoint)) {
          classes.push(className)
        }
      }
    }
    
    return classes.join(' ')
  }

  // 响应式值获取
  const getResponsiveValue = <T>(values: Partial<Record<Breakpoint | 'default', T>>): T => {
    const bpKeys = Object.keys(breakpoints) as Breakpoint[]
    
    // 从大到小检查断点
    for (let i = bpKeys.length - 1; i >= 0; i--) {
      const bp = bpKeys[i]
      if (values[bp] !== undefined && windowWidth.value >= breakpoints[bp]) {
        return values[bp]!
      }
    }
    
    // 返回默认值
    return values.default as T
  }

  // 网格列数计算
  const getGridCols = (config: Partial<Record<Breakpoint, number>> & { default: number }) => {
    return getResponsiveValue(config)
  }

  // 间距计算
  const getSpacing = (config: Partial<Record<Breakpoint, number | string>> & { default: number | string }) => {
    return getResponsiveValue(config)
  }

  // 字体大小计算
  const getFontSize = (config: Partial<Record<Breakpoint, string>> & { default: string }) => {
    return getResponsiveValue(config)
  }

  // 组件尺寸计算
  const getComponentSize = (): 'small' | 'middle' | 'large' => {
    if (isMobile.value) return 'small'
    if (isTablet.value) return 'middle'
    return 'large'
  }

  // 表格滚动配置
  const getTableScroll = (minWidth = 800) => {
    return {
      x: isMobile.value ? minWidth : undefined,
      y: isMobile.value ? 400 : 600
    }
  }

  // 模态框配置
  const getModalConfig = () => {
    return {
      width: getResponsiveValue<string | number>({
        xs: '95%',
        sm: '90%',
        md: '80%',
        lg: 800,
        xl: 1000,
        default: 800
      }),
      centered: isMobile.value,
      destroyOnClose: true
    }
  }

  // 抽屉配置
  const getDrawerConfig = () => {
    return {
      width: getResponsiveValue<string | number>({
        xs: '100%',
        sm: '90%',
        md: '70%',
        lg: 500,
        xl: 600,
        default: 500
      }),
      placement: isMobile.value ? 'bottom' : 'right' as const,
      height: isMobile.value ? '80%' : undefined
    }
  }

  // 卡片配置
  const getCardConfig = () => {
    return {
      size: getComponentSize(),
      bordered: !isMobile.value,
      hoverable: !isMobile.value
    }
  }

  // 表单配置
  const getFormConfig = () => {
    return {
      layout: isMobile.value ? 'vertical' : 'horizontal' as const,
      labelCol: isMobile.value ? undefined : { span: 6 },
      wrapperCol: isMobile.value ? undefined : { span: 18 },
      size: getComponentSize()
    }
  }

  // 生命周期管理
  onMounted(() => {
    // 初始化宽度
    updateWidth()
    
    // 添加监听器（全局共享）
    if (listenersCount === 0) {
      resizeListener = () => updateWidth()
      window.addEventListener('resize', resizeListener, { passive: true })
    }
    listenersCount++
  })

  onUnmounted(() => {
    listenersCount--
    
    // 移除监听器（当没有组件使用时）
    if (listenersCount === 0 && resizeListener) {
      window.removeEventListener('resize', resizeListener)
      resizeListener = null
    }
  })

  return {
    // 原始数据
    windowWidth: computed(() => windowWidth.value),
    currentBreakpoint,
    
    // 断点判断
    isXs,
    isSm,
    isMd,
    isLg,
    isXl,
    isXxl,
    
    // 设备类型判断
    isMobile,
    isTablet,
    isDesktop,
    isSmallScreen,
    isLargeScreen,
    
    // 工具函数
    matches,
    getResponsiveClass,
    getResponsiveValue,
    getGridCols,
    getSpacing,
    getFontSize,
    getComponentSize,
    
    // 组件配置
    getTableScroll,
    getModalConfig,
    getDrawerConfig,
    getCardConfig,
    getFormConfig
  }
}

// 预设的响应式配置
export const responsivePresets = {
  // 网格列数
  gridCols: {
    cards: { xs: 1, sm: 2, md: 3, lg: 4, xl: 5, default: 1 },
    list: { xs: 1, sm: 1, md: 2, lg: 3, xl: 4, default: 1 },
    gallery: { xs: 2, sm: 3, md: 4, lg: 6, xl: 8, default: 2 }
  },
  
  // 间距
  spacing: {
    small: { xs: 8, sm: 12, md: 16, lg: 20, xl: 24, default: 8 },
    medium: { xs: 12, sm: 16, md: 20, lg: 24, xl: 32, default: 12 },
    large: { xs: 16, sm: 20, md: 24, lg: 32, xl: 40, default: 16 }
  },
  
  // 字体大小
  fontSize: {
    small: { xs: '12px', sm: '13px', md: '14px', default: '12px' },
    medium: { xs: '14px', sm: '15px', md: '16px', default: '14px' },
    large: { xs: '16px', sm: '18px', md: '20px', default: '16px' },
    title: { xs: '20px', sm: '24px', md: '28px', lg: '32px', default: '20px' }
  }
}

// 导出断点常量
export { breakpoints as BREAKPOINTS }
