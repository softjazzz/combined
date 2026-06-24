<template>
  <div 
    ref="containerRef" 
    class="virtual-list-container"
    :style="{ height: containerHeight + 'px' }"
    @scroll="handleScroll"
  >
    <!-- 占位元素，用于撑开滚动条 -->
    <div 
      class="virtual-list-spacer"
      :style="{ height: totalHeight + 'px' }"
    />
    
    <!-- 可视区域内的实际元素 -->
    <div 
      class="virtual-list-content"
      :style="{ 
        transform: `translateY(${offsetY}px)`,
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0
      }"
    >
      <div
        v-for="item in visibleItems"
        :key="getItemKey(item.data)"
        class="virtual-list-item"
        :style="{ height: itemHeight + 'px' }"
      >
        <slot
          :item="item.data"
          :index="item.index"
        />
      </div>
    </div>
    
    <!-- 加载更多指示器 -->
    <div 
      v-if="loading" 
      class="virtual-list-loading"
      :style="{ 
        position: 'absolute',
        bottom: '10px',
        left: '50%',
        transform: 'translateX(-50%)'
      }"
    >
      <a-spin size="small" />
      <span class="ml-2">加载中...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'

// Props 定义
interface Props {
  items: Array<Record<string, unknown>>
  itemHeight: number
  containerHeight: number
  buffer?: number
  keyField?: string
  loading?: boolean
  hasMore?: boolean
  loadMore?: () => Promise<void>
}

const props = withDefaults(defineProps<Props>(), {
  items: () => [] as Array<Record<string, unknown>>,
  buffer: 5,
  keyField: 'id',
  loading: false,
  hasMore: false
})

// Emits 定义
const emit = defineEmits<{
  scroll: [{ scrollTop: number; scrollLeft: number }]
  loadMore: []
}>()

// 响应式数据
const containerRef = ref<HTMLElement>()
const scrollTop = ref(0)
const isLoadingMore = ref(false)

// 计算属性
const totalHeight = computed(() => props.items.length * props.itemHeight)

const visibleCount = computed(() => 
  Math.ceil(props.containerHeight / props.itemHeight) + props.buffer * 2
)

const startIndex = computed(() => 
  Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.buffer)
)

const endIndex = computed(() => 
  Math.min(props.items.length, startIndex.value + visibleCount.value)
)

const visibleItems = computed(() => {
  const items: Array<{ index: number; data: Record<string, unknown> }> = []
  for (let i = startIndex.value; i < endIndex.value; i++) {
    if (props.items[i]) {
      items.push({
        index: i,
        data: props.items[i]
      })
    }
  }
  return items
})

const offsetY = computed(() => startIndex.value * props.itemHeight)

// 方法
const getItemKey = (item: Record<string, unknown>): string | number => {
  return (item[props.keyField] as string | number | undefined)
    ?? (item.id as string | number | undefined)
    ?? JSON.stringify(item)
}

const handleScroll = async (event: Event) => {
  const target = event.target as HTMLElement
  scrollTop.value = target.scrollTop
  
  emit('scroll', {
    scrollTop: target.scrollTop,
    scrollLeft: target.scrollLeft
  })
  
  // 检查是否需要加载更多
  if (
    props.hasMore && 
    !props.loading && 
    !isLoadingMore.value &&
    props.loadMore &&
    target.scrollTop + target.clientHeight >= target.scrollHeight - 100
  ) {
    isLoadingMore.value = true
    try {
      await props.loadMore()
    } finally {
      isLoadingMore.value = false
    }
    emit('loadMore')
  }
}

const scrollTo = (index: number) => {
  if (containerRef.value) {
    const targetScrollTop = index * props.itemHeight
    containerRef.value.scrollTop = targetScrollTop
    scrollTop.value = targetScrollTop
  }
}

const scrollToTop = () => {
  scrollTo(0)
}

const scrollToBottom = () => {
  scrollTo(props.items.length - 1)
}

// 监听数据变化
watch(() => props.items.length, async () => {
  await nextTick()
  // 数据变化后重新计算可视区域
})

// 暴露方法给父组件
defineExpose({
  scrollTo,
  scrollToTop,
  scrollToBottom
})

// 生命周期
onMounted(() => {
  // 初始化时确保容器正确设置
  if (containerRef.value) {
    containerRef.value.scrollTop = 0
  }
})

onUnmounted(() => {
  // 清理工作
})
</script>

<style scoped>
.virtual-list-container {
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
}

.virtual-list-spacer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  pointer-events: none;
}

.virtual-list-content {
  will-change: transform;
}

.virtual-list-item {
  box-sizing: border-box;
}

.virtual-list-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  color: #666;
  font-size: 14px;
}

/* 滚动条样式优化 */
.virtual-list-container::-webkit-scrollbar {
  width: 6px;
}

.virtual-list-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.virtual-list-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.virtual-list-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .virtual-list-container::-webkit-scrollbar {
    width: 4px;
  }
  
  .virtual-list-loading {
    font-size: 12px;
    padding: 8px;
  }
}
</style>
