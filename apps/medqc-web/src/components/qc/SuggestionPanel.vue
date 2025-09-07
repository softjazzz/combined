<template>
  <div class="suggestion-panel">
    <div class="space-y-6">
      <!-- 标题和统计 -->
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-2">
            <BulbOutlined class="text-yellow-400" />
            AI 改进建议
          </h3>
          <p class="text-sm text-slate-400">基于质控分析结果，为您提供专业的改进建议</p>
        </div>
        <div class="flex items-center gap-4">
          <div class="text-center">
            <div class="text-xl font-bold text-red-400">{{ highPrioritySuggestions.length }}</div>
            <div class="text-xs text-slate-400">高优先级</div>
          </div>
          <div class="text-center">
            <div class="text-xl font-bold text-amber-400">{{ mediumPrioritySuggestions.length }}</div>
            <div class="text-xs text-slate-400">中优先级</div>
          </div>
          <div class="text-center">
            <div class="text-xl font-bold text-blue-400">{{ lowPrioritySuggestions.length }}</div>
            <div class="text-xs text-slate-400">低优先级</div>
          </div>
        </div>
      </div>

      <!-- 筛选和排序 -->
      <div class="flex items-center justify-between p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
        <div class="flex items-center gap-3">
          <span class="text-sm text-slate-300">筛选：</span>
          <a-select
            v-model:value="selectedCategory"
            size="small"
            style="width: 120px"
            @change="filterSuggestions"
            class="category-filter"
          >
            <a-select-option value="all">全部类别</a-select-option>
            <a-select-option 
              v-for="category in categories" 
              :key="category" 
              :value="category"
            >
              {{ category }}
            </a-select-option>
          </a-select>
          
          <a-select
            v-model:value="selectedPriority"
            size="small"
            style="width: 100px"
            @change="filterSuggestions"
            class="priority-filter"
          >
            <a-select-option value="all">全部优先级</a-select-option>
            <a-select-option value="high">高优先级</a-select-option>
            <a-select-option value="medium">中优先级</a-select-option>
            <a-select-option value="low">低优先级</a-select-option>
          </a-select>
        </div>

        <div class="flex items-center gap-2">
          <span class="text-sm text-slate-300">排序：</span>
          <a-select
            v-model:value="sortBy"
            size="small"
            style="width: 100px"
            @change="sortSuggestions"
            class="sort-filter"
          >
            <a-select-option value="priority">优先级</a-select-option>
            <a-select-option value="category">类别</a-select-option>
            <a-select-option value="title">标题</a-select-option>
          </a-select>
        </div>
      </div>

      <!-- 建议列表 -->
      <div class="space-y-4">
        <div
          v-for="(suggestion, index) in filteredSuggestions"
          :key="suggestion.id"
          class="suggestion-card p-5 rounded-xl border transition-all duration-300 hover:shadow-lg cursor-pointer"
          :class="getSuggestionCardClass(suggestion.priority)"
          @click="toggleSuggestionExpand(suggestion.id)"
        >
          <div class="flex items-start gap-4">
            <!-- 优先级图标 -->
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
              :class="getPriorityIconClass(suggestion.priority)"
            >
              <component :is="getPriorityIcon(suggestion.priority)" class="text-sm" />
            </div>

            <div class="flex-1 min-w-0">
              <!-- 标题和优先级 -->
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                  <h4 class="font-semibold text-slate-100 text-base">{{ suggestion.title }}</h4>
                  <a-tag 
                    :color="getPriorityColor(suggestion.priority)" 
                    size="small"
                    class="priority-tag"
                  >
                    {{ getPriorityLabel(suggestion.priority) }}
                  </a-tag>
                </div>
                <div class="flex items-center gap-2">
                  <a-tag 
                    color="blue" 
                    size="small"
                    class="category-tag"
                  >
                    {{ suggestion.category }}
                  </a-tag>
                  <div 
                    class="w-6 h-6 rounded-full bg-slate-600/50 flex items-center justify-center cursor-pointer hover:bg-slate-600/70 transition-colors"
                    :class="{ 'rotate-180': expandedSuggestions.includes(suggestion.id) }"
                  >
                    <DownOutlined class="text-xs text-slate-400" />
                  </div>
                </div>
              </div>

              <!-- 描述 -->
              <p class="text-sm text-slate-300 mb-4 leading-relaxed">{{ suggestion.description }}</p>

              <!-- 展开内容 -->
              <div 
                v-if="expandedSuggestions.includes(suggestion.id)"
                class="expanded-content"
              >
                <!-- 详细建议 -->
                <div class="mb-4 p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
                  <h5 class="text-sm font-medium text-slate-200 mb-2 flex items-center gap-2">
                    <CheckCircleOutlined class="text-emerald-400" />
                    具体实施建议
                  </h5>
                  <div class="text-sm text-slate-300 space-y-2">
                    <div v-for="(step, stepIndex) in getImplementationSteps(suggestion)" :key="stepIndex" class="flex items-start gap-2">
                      <div class="w-5 h-5 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span class="text-xs text-cyan-400 font-medium">{{ stepIndex + 1 }}</span>
                      </div>
                      <span>{{ step }}</span>
                    </div>
                  </div>
                </div>

                <!-- 相关资源 -->
                <div class="mb-4 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <h5 class="text-sm font-medium text-blue-200 mb-2 flex items-center gap-2">
                    <BookOutlined class="text-blue-400" />
                    参考资源
                  </h5>
                  <div class="space-y-2">
                    <div v-for="resource in getRelatedResources(suggestion)" :key="resource.title" class="flex items-center gap-2">
                      <LinkOutlined class="text-blue-400 text-xs" />
                      <a href="#" class="text-sm text-blue-300 hover:text-blue-200 transition-colors">{{ resource.title }}</a>
                    </div>
                  </div>
                </div>

                <!-- 预期效果 -->
                <div class="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <h5 class="text-sm font-medium text-emerald-200 mb-2 flex items-center gap-2">
                    <TrophyOutlined class="text-emerald-400" />
                    预期改进效果
                  </h5>
                  <div class="text-sm text-emerald-300">
                    {{ getExpectedImprovement(suggestion) }}
                  </div>
                </div>

                <!-- 操作按钮 -->
                <div class="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-600/30">
                  <a-button 
                    size="small"
                    @click.stop="markAsImplemented(suggestion)"
                    class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30"
                  >
                    <CheckOutlined />
                    标记已实施
                  </a-button>
                  <a-button 
                    size="small"
                    @click.stop="saveSuggestion(suggestion)"
                    class="bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30"
                  >
                    <BookmarkOutlined />
                    保存建议
                  </a-button>
                  <a-button 
                    size="small"
                    @click.stop="shareSuggestion(suggestion)"
                    class="bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30"
                  >
                    <ShareAltOutlined />
                    分享
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredSuggestions.length === 0" class="text-center py-12">
        <div class="w-20 h-20 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-4">
          <BulbOutlined class="text-slate-400 text-3xl" />
        </div>
        <div class="text-slate-400 mb-2">暂无匹配的改进建议</div>
        <div class="text-sm text-slate-500">尝试调整筛选条件或查看全部建议</div>
      </div>

      <!-- 批量操作 -->
      <div v-if="suggestions.length > 0" class="flex items-center justify-center gap-3 pt-6 border-t border-slate-700/50">
        <a-button 
          @click="expandAll"
          class="bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50"
        >
          <ExpandOutlined />
          展开全部
        </a-button>
        <a-button 
          @click="collapseAll"
          class="bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50"
        >
          <CompressOutlined />
          收起全部
        </a-button>
        <a-button 
          @click="exportSuggestions"
          class="bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30"
        >
          <ExportOutlined />
          导出建议
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  BulbOutlined,
  DownOutlined,
  CheckCircleOutlined,
  BookOutlined,
  LinkOutlined,
  TrophyOutlined,
  CheckOutlined,
  BookmarkOutlined,
  ShareAltOutlined,
  ExpandOutlined,
  CompressOutlined,
  ExportOutlined,
  ExclamationOutlined,
  StarOutlined,
  FlagOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  suggestions: Array<{
    id: string
    category: string
    title: string
    description: string
    priority: 'high' | 'medium' | 'low'
  }>
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  'suggestion-implemented': [suggestionId: string]
  'suggestion-saved': [suggestionId: string]
}>()

// 状态
const selectedCategory = ref('all')
const selectedPriority = ref('all')
const sortBy = ref('priority')
const expandedSuggestions = ref<string[]>([])

// 计算属性
const categories = computed(() => {
  const cats = [...new Set(props.suggestions.map(s => s.category))]
  return cats.sort()
})

const highPrioritySuggestions = computed(() => 
  props.suggestions.filter(s => s.priority === 'high')
)

const mediumPrioritySuggestions = computed(() => 
  props.suggestions.filter(s => s.priority === 'medium')
)

const lowPrioritySuggestions = computed(() => 
  props.suggestions.filter(s => s.priority === 'low')
)

const filteredSuggestions = computed(() => {
  let filtered = props.suggestions

  // 按类别筛选
  if (selectedCategory.value !== 'all') {
    filtered = filtered.filter(s => s.category === selectedCategory.value)
  }

  // 按优先级筛选
  if (selectedPriority.value !== 'all') {
    filtered = filtered.filter(s => s.priority === selectedPriority.value)
  }

  // 排序
  filtered.sort((a, b) => {
    switch (sortBy.value) {
      case 'priority':
        const priorityOrder = { high: 3, medium: 2, low: 1 }
        return priorityOrder[b.priority] - priorityOrder[a.priority]
      case 'category':
        return a.category.localeCompare(b.category)
      case 'title':
        return a.title.localeCompare(b.title)
      default:
        return 0
    }
  })

  return filtered
})

// 方法
const filterSuggestions = () => {
  // 筛选逻辑已在 computed 中处理
}

const sortSuggestions = () => {
  // 排序逻辑已在 computed 中处理
}

const toggleSuggestionExpand = (suggestionId: string) => {
  const index = expandedSuggestions.value.indexOf(suggestionId)
  if (index > -1) {
    expandedSuggestions.value.splice(index, 1)
  } else {
    expandedSuggestions.value.push(suggestionId)
  }
}

const expandAll = () => {
  expandedSuggestions.value = filteredSuggestions.value.map(s => s.id)
}

const collapseAll = () => {
  expandedSuggestions.value = []
}

const getPriorityColor = (priority: string) => {
  const colors = {
    high: 'red',
    medium: 'orange',
    low: 'blue'
  }
  return colors[priority as keyof typeof colors] || 'default'
}

const getPriorityLabel = (priority: string) => {
  const labels = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级'
  }
  return labels[priority as keyof typeof labels] || priority
}

const getPriorityIcon = (priority: string) => {
  const icons = {
    high: ExclamationOutlined,
    medium: StarOutlined,
    low: FlagOutlined
  }
  return icons[priority as keyof typeof icons] || FlagOutlined
}

const getPriorityIconClass = (priority: string) => {
  const classes = {
    high: 'bg-red-500/20 text-red-400 border border-red-500/30',
    medium: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
    low: 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
  }
  return classes[priority as keyof typeof classes] || 'bg-gray-500/20 text-gray-400'
}

const getSuggestionCardClass = (priority: string) => {
  const classes = {
    high: 'border-red-500/30 bg-red-500/5 hover:border-red-500/50 hover:bg-red-500/10',
    medium: 'border-orange-500/30 bg-orange-500/5 hover:border-orange-500/50 hover:bg-orange-500/10',
    low: 'border-blue-500/30 bg-blue-500/5 hover:border-blue-500/50 hover:bg-blue-500/10'
  }
  return classes[priority as keyof typeof classes] || 'border-slate-600/30 bg-slate-700/5'
}

const getImplementationSteps = (suggestion) => {
  // 模拟实施步骤，实际应用中应该从后端获取
  const steps = [
    '仔细审查当前病案记录中的相关部分',
    '参考医疗标准和最佳实践指南',
    '与相关科室医生讨论具体改进方案',
    '更新病案记录并记录改进过程',
    '定期回顾改进效果并持续优化'
  ]
  return steps.slice(0, Math.floor(Math.random() * 3) + 3)
}

const getRelatedResources = (suggestion) => {
  // 模拟相关资源，实际应用中应该从后端获取
  return [
    { title: '医疗质量管理规范', url: '#' },
    { title: '病案书写基本规范', url: '#' },
    { title: '临床诊疗指南', url: '#' }
  ]
}

const getExpectedImprovement = (suggestion) => {
  const improvements = [
    '提高病案记录的完整性和准确性，预计质控评分提升5-10分',
    '减少医疗风险，提升患者安全保障水平',
    '优化诊疗流程，提高医疗服务质量和效率',
    '符合医疗质量标准要求，通过相关审核检查'
  ]
  return improvements[Math.floor(Math.random() * improvements.length)]
}

const markAsImplemented = (suggestion) => {
  message.success(`建议"${suggestion.title}"已标记为已实施`)
  emit('suggestion-implemented', suggestion.id)
}

const saveSuggestion = (suggestion) => {
  message.success(`建议"${suggestion.title}"已保存`)
  emit('suggestion-saved', suggestion.id)
}

const shareSuggestion = (suggestion) => {
  // 模拟分享功能
  if (navigator.share) {
    navigator.share({
      title: suggestion.title,
      text: suggestion.description,
      url: window.location.href
    })
  } else {
    // 复制到剪贴板
    navigator.clipboard.writeText(`${suggestion.title}\n${suggestion.description}`)
    message.success('建议内容已复制到剪贴板')
  }
}

const exportSuggestions = () => {
  message.info('导出功能开发中...')
}
</script>

<style scoped>
.suggestion-card {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.suggestion-card:hover {
  transform: translateY(-2px);
}

.expanded-content {
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    max-height: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    max-height: 1000px;
    transform: translateY(0);
  }
}

.priority-tag,
.category-tag {
  border: none !important;
  border-radius: 0.5rem !important;
  font-weight: 600 !important;
  font-size: 10px !important;
}

/* 筛选器样式 */
:deep(.category-filter .ant-select-selector),
:deep(.priority-filter .ant-select-selector),
:deep(.sort-filter .ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

/* 展开/收起图标动画 */
.rotate-180 {
  transform: rotate(180deg);
  transition: transform 0.3s ease;
}

/* 按钮样式 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .flex.items-center.justify-between {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  
  .suggestion-card {
    padding: 1rem;
  }
  
  .w-10.h-10 {
    width: 2rem;
    height: 2rem;
  }
}
</style>
