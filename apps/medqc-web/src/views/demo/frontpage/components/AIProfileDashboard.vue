<template>
                    <div class="h-full">
                       <div v-if="!profile" class="h-full flex flex-col items-center justify-center text-center p-6">
                           <div class="w-16 h-16 bg-blue-50 dark:bg-blue-900/20 rounded-2xl mb-4 flex items-center justify-center">
                              <ScanOutlined class="text-3xl text-blue-500" />
                           </div>
                           <h3 class="text-lg font-medium text-slate-800 dark:text-white mb-2">AI 深度画像分析</h3>
                           <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">对病历全文进行深度阅读，构建诊断发生发展时间轴，验证手术闭环完整性，并自动发现首页填报差异。</p>
                           <button @click="analyzeProfile" :disabled="!medicalText" class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2.5 rounded-xl text-sm font-medium transition-colors">
                              {{ profileLoading ? '正在分析...' : '开始深度分析' }}
                           </button>
                       </div>
                       <div v-else class="h-full overflow-hidden flex flex-col">
                           <!-- Dashboard grid -->
                           <div class="h-full p-4 overflow-y-auto custom-scrollbar flex flex-col">
                              <!-- Stats Cards Removed as per request -->
                              
                              <div class="flex flex-col lg:grid lg:grid-cols-12 gap-4 flex-1 min-h-[600px]">
                                <!-- Left: Problem List -->
                                <div class="col-span-12 lg:col-span-3 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 flex flex-col">
                                   <div class="p-3 border-b border-slate-100 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-200">
                                      问题列表
                                   </div>
                                   <div class="flex-1 overflow-y-auto p-2 space-y-2">
                                      <div class="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30 cursor-pointer hover:shadow-md transition-all">
                                         <div class="flex justify-between items-start mb-1">
                                            <span class="font-medium text-red-700 dark:text-red-300 text-sm">高血压3级 极高危</span>
                                            <ExclamationCircleOutlined class="text-red-500" />
                                         </div>
                                         <div class="text-xs text-red-500/80">I10.x00</div>
                                      </div>
                                      <div class="p-3 bg-slate-50 dark:bg-slate-700/30 rounded-lg border border-slate-100 dark:border-slate-700 cursor-pointer hover:shadow-md transition-all">
                                         <div class="flex justify-between items-start mb-1">
                                            <span class="font-medium text-slate-700 dark:text-slate-200 text-sm">2型糖尿病</span>
                                         </div>
                                         <div class="text-xs text-slate-500">E11.900</div>
                                      </div>
                                      <div class="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/30 cursor-pointer hover:shadow-md transition-all">
                                         <div class="flex justify-between items-start mb-1">
                                            <span class="font-medium text-yellow-700 dark:text-yellow-300 text-sm">冠心病 (待查)</span>
                                            <QuestionCircleOutlined class="text-yellow-500" />
                                         </div>
                                         <div class="text-xs text-yellow-500/80">疑似诊断</div>
                                      </div>
                                   </div>
                                </div>
                                
                                <!-- Center: 3D Body Model -->
                                <div class="col-span-12 lg:col-span-5 bg-gradient-to-b from-slate-900 to-slate-800 rounded-xl shadow-sm border border-slate-700 flex flex-col relative overflow-hidden group min-h-[280px]">
                                   <div class="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
                                   <div class="absolute top-4 left-4 text-white/50 text-xs font-mono uppercase tracking-widest z-10">AI 人体透视</div>
                                   
                                   <!-- QC Details Button -->
                                   <div class="absolute bottom-4 right-4 z-30">
                                      <button @click="showQCModal" class="bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 group">
                                         <FileTextOutlined class="group-hover:text-blue-400 transition-colors" />
                                         质控详情报告
                                      </button>
                                   </div>
                                   
                                   <div class="flex-1 flex items-center justify-center relative">
                                      <!-- Body Image -->
                                      <img src="/human_body_schematic.png" class="h-[90%] object-contain drop-shadow-[0_0_15px_rgba(59,130,246,0.5)] opacity-90" alt="Body Map" />
                                      
                                      <!-- Dynamic Hotspots with Staggered Animation -->
                                      <template v-for="(marker, index) in currentBodyMarkers" :key="index">
                                        <!-- Marker Container with Staggered Entry -->
                                        <div 
                                          class="absolute cursor-pointer z-20 transition-all duration-500"
                                          :class="[
                                            visibleMarkerIndices.includes(index) ? 'opacity-100 scale-100' : 'opacity-0 scale-0'
                                          ]"
                                          :style="{ 
                                            top: getMarkerPosition(marker, 'top'), 
                                            left: getMarkerPosition(marker, 'left'),
                                            transitionDelay: `${index * 300}ms`
                                          }"
                                          @click="setActiveMarker(index)"
                                        >
                                          <!-- Ping animation for active/severe markers -->
                                          <div 
                                            v-if="activeMarkerIndex === index || marker.severity === 'severe'" 
                                            class="rounded-full animate-ping absolute opacity-75"
                                            :class="[
                                              getSeverityColor(marker.severity),
                                              activeMarkerIndex === index ? 'w-6 h-6 -ml-1 -mt-1' : 'w-4 h-4'
                                            ]"
                                          ></div>
                                          <!-- Marker dot -->
                                          <div 
                                            class="rounded-full border-2 border-white shadow-lg relative z-10 transition-all duration-300"
                                            :class="[
                                              getSeverityColor(marker.severity),
                                              activeMarkerIndex === index ? 'w-5 h-5 ring-4 ring-white/30' : 'w-3 h-3'
                                            ]"
                                          ></div>
                                        </div>
                                        
                                        <!-- Connection Line (SVG) -->
                                        <svg 
                                          v-if="activeMarkerIndex === index && visibleMarkerIndices.includes(index)"
                                          class="absolute inset-0 w-full h-full pointer-events-none z-10 overflow-visible"
                                        >
                                          <line 
                                            :x1="getMarkerPosition(marker, 'left')" 
                                            :y1="getMarkerPosition(marker, 'top')"
                                            x2="5%" 
                                            y2="50%"
                                            :stroke="marker.severity === 'severe' ? '#ef4444' : marker.severity === 'moderate' ? '#eab308' : '#60a5fa'"
                                            stroke-width="2"
                                            stroke-dasharray="5,5"
                                            class="animate-pulse"
                                          />
                                        </svg>
                                      </template>
                                      
                                      <!-- Navigation dots -->
                                      <div 
                                        v-if="currentBodyMarkers.length > 1"
                                        class="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-30"
                                      >
                                        <button 
                                          v-for="(_, idx) in currentBodyMarkers" 
                                          :key="idx"
                                          @click="setActiveMarker(idx)"
                                          class="w-2 h-2 rounded-full transition-all duration-300"
                                          :class="activeMarkerIndex === idx ? 'bg-white w-6' : 'bg-white/50 hover:bg-white/80'"
                                        ></button>
                                      </div>
                                   </div>
                                </div>
                                
                                
                                <!-- Right: Info Card Details -->
                                <div class="col-span-12 lg:col-span-4 flex flex-col">
                                   <!-- Active Marker Info Card (Moved out) -->
                                   <div 
                                     v-if="activeMarkerIndex !== null && currentBodyMarkers[activeMarkerIndex]"
                                     class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 p-4 h-full transition-all duration-500 flex flex-col"
                                     :class="visibleMarkerIndices.includes(activeMarkerIndex) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'"
                                   >
                                     <div class="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100 dark:border-slate-700">
                                       <div 
                                         class="w-3 h-3 rounded-full"
                                         :class="getSeverityColor(currentBodyMarkers[activeMarkerIndex].severity)"
                                       ></div>
                                       <span class="font-bold text-lg text-slate-800 dark:text-white">
                                         {{ getRegionLabel(currentBodyMarkers[activeMarkerIndex].region) }}
                                       </span>
                                       <span 
                                         class="ml-auto px-2 py-1 rounded-full text-xs font-medium"
                                         :class="getSeverityBadgeClass(currentBodyMarkers[activeMarkerIndex].severity)"
                                       >
                                         {{ getSeverityLabel(currentBodyMarkers[activeMarkerIndex].severity) }}
                                       </span>
                                     </div>
                                     
                                     <div class="mb-4">
                                        <div class="text-xs text-slate-400 mb-1">识别问题</div>
                                        <p class="text-base font-medium text-slate-700 dark:text-slate-200 leading-relaxed">
                                          {{ currentBodyMarkers[activeMarkerIndex].condition }}
                                        </p>
                                     </div>
                                     
                                     <!-- Related Timeline Events -->
                                     <div v-if="getRelatedTimelineEvents(currentBodyMarkers[activeMarkerIndex].condition).length > 0" class="flex-1 overflow-y-auto custom-scrollbar min-h-0">
                                        <div class="text-xs font-semibold text-slate-500 mb-2">相关诊疗事件</div>
                                        <div class="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-3">
                                           <ul class="space-y-3">
                                             <li v-for="(event, eIdx) in getRelatedTimelineEvents(currentBodyMarkers[activeMarkerIndex].condition)" :key="eIdx" class="text-xs text-slate-600 dark:text-slate-400 flex gap-2">
                                               <span class="text-blue-500 mt-0.5">•</span>
                                               <span class="">
                                                  <span class="block text-xs text-slate-400 mb-0.5">{{ event.date }}</span>
                                                  {{ event.event }}
                                               </span>
                                             </li>
                                           </ul>
                                        </div>
                                     </div>

                                     <div class="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700 flex justify-between items-center text-xs text-slate-400">
                                       <span>AI 智能分析</span>
                                       <span>{{ activeMarkerIndex + 1 }} / {{ currentBodyMarkers.length }}</span>
                                     </div>
                                   </div>
                                   
                                   <!-- Empty State -->
                                   <div v-else class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 p-8 h-full flex flex-col items-center justify-center text-center text-slate-400">
                                      <ScanOutlined class="text-4xl mb-3 opacity-20" />
                                      <p>点击左侧人体部位<br>查看详细分析</p>
                                   </div>
                                </div>
                                
                                <!-- Horizontal Timeline Below Body Model -->
                                <div v-if="profile?.diagnosis_timeline?.length" class="col-span-12 mt-4 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 p-4">
                                   <div class="flex items-center justify-between mb-3">
                                      <h4 class="font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                                         <ClockCircleOutlined class="text-blue-500" />
                                         诊断发生发展时间轴
                                      </h4>
                                      <span class="text-xs text-slate-400">{{ profile.diagnosis_timeline.length }} 个事件</span>
                                   </div>
                                   <div class="overflow-x-auto pb-2 custom-scrollbar">
                                      <div class="flex gap-4 min-w-max">
                                         <div 
                                           v-for="(event, idx) in profile.diagnosis_timeline" 
                                           :key="idx"
                                           class="flex-shrink-0 w-48 bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3 border-l-4 transition-all hover:shadow-md"
                                           :class="[
                                             event.severity === 'critical' || event.severity === 'severe' ? 'border-red-500' : 
                                             event.severity === 'moderate' ? 'border-yellow-500' : 'border-blue-500'
                                           ]"
                                         >
                                           <div class="text-xs text-slate-400 mb-1">{{ event.date }}</div>
                                           <div class="text-sm font-medium text-slate-700 dark:text-slate-200 line-clamp-2">{{ event.event }}</div>
                                           <div class="mt-2 flex items-center gap-2">
                                             <span 
                                               class="text-xs px-1.5 py-0.5 rounded"
                                               :class="[
                                                 event.type === 'diagnosis' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' :
                                                 event.type === 'treatment' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                                                 event.type === 'examination' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
                                                 'bg-slate-100 text-slate-700 dark:bg-slate-600 dark:text-slate-300'
                                               ]"
                                             >{{ event.type === 'diagnosis' ? '诊断' : event.type === 'treatment' ? '治疗' : event.type === 'examination' ? '检查' : '症状' }}</span>
                                           </div>
                                         </div>
                                      </div>
                                   </div>
                                </div>
                                
                                <!-- QC Report Modal -->
                                <a-modal v-model:open="isQCModalVisible" title="AI 质控详情报告" width="800px" :footer="null">
                                   <a-tabs default-active-key="1">
                                      <a-tab-pane key="1" tab="诊断发生发展时间轴">
                                         <div class="max-h-[500px] overflow-y-auto p-4">
                                            <a-timeline mode="left">
                                               <a-timeline-item v-for="(event, idx) in profile?.diagnosis_timeline" :key="idx" :color="event.severity === 'critical' || event.severity === 'severe' ? 'red' : 'blue'">
                                                  <template #label>
                                                    <span class="text-slate-500 text-xs">{{ event.date }}</span>
                                                  </template>
                                                  <div class="font-medium text-slate-800 dark:text-slate-200">{{ event.event }}</div>
                                                  <div class="text-xs text-slate-500 mt-1">
                                                    <span class="capitalize bg-slate-100 dark:bg-slate-800 px-1.5 rounded">{{ event.type }}</span>
                                                  </div>
                                               </a-timeline-item>
                                            </a-timeline>
                                         </div>
                                      </a-tab-pane>
                                      <a-tab-pane key="2" tab="首页填报差异验证">
                                         <div class="max-h-[500px] overflow-y-auto p-4">
                                            <div v-if="!profile?.discrepancies || profile.discrepancies.length === 0" class="text-center text-slate-400 p-8">
                                               <CheckCircleOutlined class="text-4xl text-green-500 mb-2" />
                                               <div>未发现显著填报问题</div>
                                            </div>
                                            <a-list v-else item-layout="horizontal" :data-source="profile.discrepancies">
                                               <template #renderItem="{ item }">
                                                  <a-list-item class="border-b border-slate-100 dark:border-slate-700 px-2 py-3">
                                                     <a-list-item-meta>
                                                        <template #title>
                                                           <span class="text-slate-800 dark:text-slate-200 font-medium">{{ item.field }}</span>
                                                           <span class="ml-2 px-2 py-0.5 rounded text-xs" :class="item.type === 'missing' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'">
                                                              {{ item.type === 'missing' ? '漏填' : '不一致' }}
                                                           </span>
                                                        </template>
                                                        <template #description>
                                                           <div class="text-slate-600 dark:text-slate-400 mt-1">
                                                              <div class="mb-1"><span class="text-slate-400">问题:</span> {{ item.description }}</div>
                                                              <div class="text-blue-600 dark:text-blue-400"><span class="text-slate-400"> 建议:</span> {{ item.suggestion }}</div>
                                                           </div>
                                                        </template>
                                                     </a-list-item-meta>
                                                  </a-list-item>
                                               </template>
                                            </a-list>
                                         </div>
                                      </a-tab-pane>
                                   </a-tabs>
                                </a-modal>
                                
                                <!-- Right: Vitals & Labs Removed as per request -->
                              </div>
                           </div>
                       </div>
                    </div>

</template>


<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  ScanOutlined
} from '@ant-design/icons-vue'

const emit = defineEmits<{
  (e: 'expand'): void
}>()

const props = defineProps<{
  medicalText?: string
  frontpage?: any | null
}>()

const frontpage = computed(() => props.frontpage || null)

const profile = ref<any>(null)
const profileLoading = ref(false)

// Body marker animation state
const activeMarkerIndex = ref<number | null>(0)
const visibleMarkerIndices = ref<number[]>([])
const markerAnimationTimer = ref<number | null>(null)

// Default body markers (used before LLM analysis)
const defaultBodyMarkers = [
  { region: 'heart', condition: '冠状动脉粥样硬化', severity: 'severe', position: { top: '32%', left: '52%' } },
  { region: 'pancreas', condition: '2型糖尿病', severity: 'moderate', position: { top: '45%', left: '55%' } }
]

const currentBodyMarkers = computed(() => profile.value?.body_markers || defaultBodyMarkers)

const isQCModalVisible = ref(false)

const showQCModal = () => {
  isQCModalVisible.value = true
}

const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'severe': return 'bg-red-500'
    case 'moderate': return 'bg-yellow-500'
    case 'mild': return 'bg-blue-400'
    default: return 'bg-slate-400'
  }
}

const getRegionLabel = (region: string): string => {
  const labels: Record<string, string> = {
    heart: '心脏',
    lung: '肺部',
    liver: '肝脏',
    kidney: '肾脏',
    brain: '脑部',
    pancreas: '胰腺',
    stomach: '胃部'
  }
  return labels[region] || region
}

// Fixed coordinates for each region to ensure accurate positioning
const REGION_COORDINATES: Record<string, { top: string, left: string }> = {
  brain: { top: '8%', left: '50%' },
  lung: { top: '25%', left: '48%' }, // Slightly offset to avoid center overlapping
  heart: { top: '28%', left: '55%' }, // Heart is typically on the left side of the body (right side of image)
  liver: { top: '40%', left: '45%' },
  stomach: { top: '42%', left: '54%' },
  pancreas: { top: '44%', left: '52%' },
  kidney: { top: '48%', left: '42%' },
  intestine: { top: '55%', left: '50%' },
  spine: { top: '35%', left: '50%' }
}

const getMarkerPosition = (marker: any, axis: 'top' | 'left'): string => {
  // First try to resolve valid region-based coordinates
  if (marker.region && REGION_COORDINATES[marker.region]) {
    return REGION_COORDINATES[marker.region][axis]
  }

  // Fallback to coordinates provided in marker object if available
  const pos = marker.position?.[axis]
  if (typeof pos === 'number') return `${pos}%`
  if (typeof pos === 'string') return pos
  
  return '50%'
}

const getSeverityBadgeClass = (severity: string): string => {
  switch (severity) {
    case 'severe': return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    case 'moderate': return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'mild': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
    default: return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400'
  }
}

const getSeverityLabel = (severity: string): string => {
  switch (severity) {
    case 'severe': return '严重'
    case 'moderate': return '中度'
    case 'mild': return '轻度'
    default: return '未知'
  }
}

const setActiveMarker = (index: number) => {
  activeMarkerIndex.value = index
}

const stopMarkerAnimation = () => {
  if (markerAnimationTimer.value) {
    clearInterval(markerAnimationTimer.value)
    markerAnimationTimer.value = null
  }
}

const startMarkerAnimation = () => {
  stopMarkerAnimation()
  visibleMarkerIndices.value = []
  activeMarkerIndex.value = 0

  const markers = currentBodyMarkers.value
  markers.forEach((_: any, idx: number) => {
    setTimeout(() => {
      visibleMarkerIndices.value.push(idx)
    }, idx * 500 + 300)
  })

  setTimeout(() => {
    markerAnimationTimer.value = window.setInterval(() => {
      if (activeMarkerIndex.value === null) {
        activeMarkerIndex.value = 0
      } else {
        activeMarkerIndex.value = (activeMarkerIndex.value + 1) % markers.length
      }
    }, 3000)
  }, markers.length * 500 + 1000)
}

const getRelatedTimelineEvents = (markerCondition: string) => {
  if (!profile.value?.diagnosis_timeline || !markerCondition) return []

  const keywords = markerCondition.split(/[,，\s]/).filter((k: string) => k.length > 1)

  return profile.value.diagnosis_timeline
    .filter((item: any) => {
      if (keywords.some((k: string) => item.event.includes(k))) return true
      if (item.event.includes(markerCondition)) return true
      if (markerCondition.includes('心') && item.event.includes('胸闷')) return true
      return false
    })
    .slice(0, 3)
}

const analyzeProfile = async () => {
  if (!props.medicalText) return

  profileLoading.value = true
  try {
    const response = await fetch('/api/v1/case-front-page/analyze-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        medical_text: props.medicalText,
        frontpage_diagnoses: frontpage.value?.diagnoses?.discharge_main_diagnosis_text
          ? [frontpage.value.diagnoses.discharge_main_diagnosis_text]
          : [],
        frontpage_procedures: (frontpage.value as any)?.procedures?.main_procedure_text
          ? [(frontpage.value as any).procedures.main_procedure_text]
          : []
      })
    })

    const data = await response.json()

    if (data.success && data.data) {
      profile.value = data.data
      message.success('AI 画像分析完成')
      startMarkerAnimation()
      setTimeout(() => emit('expand'), 500)
    } else {
      profile.value = {
        diagnosis_timeline: [{ date: '2026-01-01', event: '因胸闷心悸入院', type: 'symptom', severity: 'moderate' }],
        vital_signs: {},
        lab_results: {},
        risk_assessment: { overall_risk_score: 85, risk_level: 'high', primary_risks: [], recommendations: [] },
        body_markers: [],
        discrepancies: []
      }
      message.warning('使用模拟分析结果')
    }
  } catch (error) {
    console.error('Profile analysis error:', error)
    message.error('分析失败，请检查网络连接')
  } finally {
    profileLoading.value = false
  }
}

watch(
  () => props.medicalText,
  () => {
    profile.value = null
    isQCModalVisible.value = false
    visibleMarkerIndices.value = []
    activeMarkerIndex.value = 0
    stopMarkerAnimation()
  }
)

onUnmounted(() => {
  stopMarkerAnimation()
})
</script>


<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
.dark .custom-scrollbar::-webkit-scrollbar-thumb {
  background: #475569;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
