<template>
  <div class="batch-rule-test-embed">
    <!-- 加载提示覆盖层 -->
    <div
      v-if="loading"
      class="loading-container"
    >
      <a-spin
        size="large"
        tip="加载中..."
      />
    </div>

    <!-- 始终渲染 iframe，避免因为 v-if 导致 onload 永远不触发 -->
    <iframe
      ref="iframeRef"
      :src="batchTestUrl"
      class="batch-test-iframe"
      frameborder="0"
      @load="onIframeLoad"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Props {
  preselectedRules?: any[]
  useDemoApi?: boolean  // 是否使用演示页面专用API
}

const props = withDefaults(defineProps<Props>(), {
  useDemoApi: true  // 默认使用演示API
})

const emit = defineEmits<{
  close: []
}>()

const loading = ref(true)
const iframeRef = ref<HTMLIFrameElement | null>(null)

// 批量测试页面URL，添加查询参数标识使用演示API
const batchTestUrl = ref(
  props.useDemoApi
    ? '/dashboard/custom-rules/batch-test?demo=true'
    : '/dashboard/custom-rules/batch-test'
)

const onIframeLoad = () => {
  loading.value = false

  // 通过postMessage传递配置给iframe
  if (iframeRef.value?.contentWindow) {
    setTimeout(() => {
      iframeRef.value?.contentWindow?.postMessage({
        type: 'BATCH_TEST_CONFIG',
        config: {
          useDemoApi: props.useDemoApi,
          preselectedRules: props.preselectedRules
        }
      }, window.location.origin)
    }, 500)
  }
}

// 监听来自iframe的消息
const handleMessage = (event: MessageEvent) => {
  if (event.origin !== window.location.origin) return

  if (event.data.type === 'CLOSE_BATCH_TEST') {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('message', handleMessage)
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})
</script>

<style scoped lang="less">
.batch-rule-test-embed {
  width: 100%;
  height: 85vh;
  min-height: 600px;
  position: relative;
  
  .loading-container {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 400px;
  }
  
  .batch-test-iframe {
    width: 100%;
    height: 100%;
    border: none;
    border-radius: 8px;
  }
}
</style>

