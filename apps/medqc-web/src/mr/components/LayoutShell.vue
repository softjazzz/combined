<template>
  <div class="layout-shell" :style="cssVars">
    <!-- Header -->
    <div class="layout-header">
      <div class="header-left">
        <a-button type="text" @click="$emit('back')" class="back-btn">
          <ArrowLeftOutlined />
          返回
        </a-button>
        <a-divider type="vertical" />
        <div class="patient-info" v-if="patient">
          <h3>{{ patient.patient_info?.name || patient.record_name || '未知患者' }}</h3>
          <span class="patient-meta">
            {{ patient.patient_info?.age }}岁 {{ patient.patient_info?.gender }} |
            {{ patient.record_number || patient.id }}
          </span>
        </div>
      </div>
      <div class="header-right">
        <a-tag :color="getStatusColor(patient?.status)">
          {{ patient?.status || '未知状态' }}
        </a-tag>
      </div>
    </div>

    <!-- Main Layout -->
    <div class="layout-main">
      <!-- Left Navigation -->
      <div 
        v-show="!collapsedNav" 
        class="layout-nav"
        :style="{ width: navWidth + 'px' }"
      >
        <slot name="nav"></slot>
      </div>

      <!-- Nav Resizer -->
      <div 
        v-show="!collapsedNav"
        class="layout-resizer nav-resizer"
        @mousedown="startResize('nav')"
      ></div>

      <!-- Center Content -->
      <div class="layout-content">
        <!-- Toolbar -->
        <div class="layout-toolbar">
          <div class="toolbar-left">
            <a-button 
              type="text" 
              size="small"
              @click="toggleNav"
              :title="collapsedNav ? '展开导航' : '收起导航'"
            >
              <MenuFoldOutlined v-if="!collapsedNav" />
              <MenuUnfoldOutlined v-if="collapsedNav" />
            </a-button>
          </div>
          
          <div class="toolbar-center">
            <slot name="toolbar"></slot>
          </div>
          
          <div class="toolbar-right">
            <a-button 
              type="text" 
              size="small"
              @click="toggleAside"
              :title="collapsedAside ? '展开侧栏' : '收起侧栏'"
            >
              <MenuFoldOutlined v-if="!collapsedAside" />
              <MenuUnfoldOutlined v-if="collapsedAside" />
            </a-button>
          </div>
        </div>

        <!-- Main Content -->
        <div class="layout-content-main">
          <slot name="content"></slot>
        </div>
      </div>

      <!-- Aside Resizer -->
      <div 
        v-show="!collapsedAside"
        class="layout-resizer aside-resizer"
        @mousedown="startResize('aside')"
      ></div>

      <!-- Right Aside -->
      <div 
        v-show="!collapsedAside" 
        class="layout-aside"
        :style="{ width: asideWidth + 'px' }"
      >
        <slot name="aside"></slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { 
  ArrowLeftOutlined, 
  MenuFoldOutlined, 
  MenuUnfoldOutlined 
} from '@ant-design/icons-vue'

interface Props {
  navWidth?: number
  asideWidth?: number
  collapsedNav?: boolean
  collapsedAside?: boolean
  patient?: any
}

const props = withDefaults(defineProps<Props>(), {
  navWidth: 280,
  asideWidth: 320,
  collapsedNav: false,
  collapsedAside: false,
  patient: null
})

const emit = defineEmits<{
  'update:navWidth': [width: number]
  'update:asideWidth': [width: number]
  'update:collapsedNav': [collapsed: boolean]
  'update:collapsedAside': [collapsed: boolean]
  'back': []
}>()

// 拖拽状态
const resizing = ref<'nav' | 'aside' | null>(null)
const startX = ref(0)
const startWidth = ref(0)

// CSS 变量
const cssVars = computed(() => ({
  '--nav-w': props.navWidth + 'px',
  '--aside-w': props.asideWidth + 'px'
}))

// 状态颜色
const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    'active': 'green',
    'completed': 'blue',
    'pending': 'orange',
    'cancelled': 'red'
  }
  return colors[status] || 'default'
}

// 折叠切换
const toggleNav = () => {
  const newValue = !props.collapsedNav
  emit('update:collapsedNav', newValue)
  localStorage.setItem('mr_collapsed_nav', String(newValue))
}

const toggleAside = () => {
  const newValue = !props.collapsedAside
  emit('update:collapsedAside', newValue)
  localStorage.setItem('mr_collapsed_aside', String(newValue))
}

// 拖拽调整宽度
const startResize = (type: 'nav' | 'aside') => {
  resizing.value = type
  startX.value = event?.clientX || 0
  startWidth.value = type === 'nav' ? props.navWidth : props.asideWidth
  
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

const handleResize = (e: MouseEvent) => {
  if (!resizing.value) return
  
  const deltaX = e.clientX - startX.value
  let newWidth = startWidth.value
  
  if (resizing.value === 'nav') {
    newWidth = startWidth.value + deltaX
    newWidth = Math.max(220, Math.min(480, newWidth))
    emit('update:navWidth', newWidth)
  } else {
    newWidth = startWidth.value - deltaX
    newWidth = Math.max(260, Math.min(480, newWidth))
    emit('update:asideWidth', newWidth)
  }
}

const stopResize = () => {
  if (resizing.value) {
    const key = resizing.value === 'nav' ? 'mr_nav_w' : 'mr_aside_w'
    const width = resizing.value === 'nav' ? props.navWidth : props.asideWidth
    localStorage.setItem(key, String(width))
  }
  
  resizing.value = null
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// 组件卸载时清理
onUnmounted(() => {
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
.layout-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.layout-header {
  height: 64px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
}

.patient-info h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.patient-meta {
  color: #666;
  font-size: 14px;
}

.layout-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.layout-nav {
  background: white;
  border-right: 1px solid #e8e8e8;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.layout-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.layout-aside {
  background: white;
  border-left: 1px solid #e8e8e8;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.layout-resizer {
  width: 4px;
  background: transparent;
  cursor: col-resize;
  position: relative;
}

.layout-resizer:hover {
  background: #1890ff;
}

.layout-toolbar {
  height: 48px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  position: sticky;
  top: 64px;
  z-index: 99;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.layout-content-main {
  flex: 1;
  overflow: auto;
  background: white;
}

/* 响应式 */
@media (max-width: 991px) {
  .layout-nav,
  .layout-aside,
  .layout-resizer {
    display: none !important;
  }
  
  .toolbar-left,
  .toolbar-right {
    display: none;
  }
}
</style>
