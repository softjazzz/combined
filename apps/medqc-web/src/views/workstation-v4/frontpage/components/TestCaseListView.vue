<template>
  <div class="h-full w-full flex flex-col bg-[#f5f5f7] p-6 overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button
        class="text-[rgba(29,29,31,0.45)] hover:text-[#2b6cf6]"
        @click="$emit('back')"
      >
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-[20px] font-semibold text-[#1d1d1f]">
        测试病历列表
      </h2>
      <span class="text-sm text-[rgba(29,29,31,0.45)]">{{ testCases.length }} 个测试病历</span>
    </div>

    <div class="flex-1 flex gap-4 overflow-hidden">
      <!-- Left: Test Case List -->
      <div
        class="w-80 flex-shrink-0 bg-white/90 rounded-2xl border border-black/[0.08] shadow-[0_1px_4px_rgba(0,0,0,0.045),0_2px_8px_rgba(0,0,0,0.035)] backdrop-blur-[18px] flex flex-col overflow-hidden"
      >
        <div class="px-4 py-3 border-b border-black/[0.08] flex items-center justify-between">
          <h3 class="text-sm font-semibold text-[#1d1d1f]">
            病历列表
          </h3>
          <button
            class="px-3 py-1.5 bg-[#2b6cf6] text-white text-xs rounded-lg hover:bg-[#0057b8] transition-colors flex items-center gap-1.5 shadow-[0_5px_14px_rgba(43,108,246,0.18)]"
            @click="showCreateModal = true"
          >
            <PlusOutlined />
            新建
          </button>
        </div>

        <div class="flex-1 overflow-y-auto">
          <div
            v-for="(testCase, index) in testCases"
            :key="index"
            :class="[
              'p-4 border-b border-black/[0.06] cursor-pointer transition-colors',
              selectedIndex === index
                ? 'bg-[rgba(43,108,246,0.08)] border-l-4 border-l-[#2b6cf6]'
                : 'hover:bg-black/[0.025]',
            ]"
            @click="selectedIndex = index"
          >
            <div class="flex items-start gap-3">
              <div
                class="w-10 h-10 rounded-lg bg-[rgba(43,108,246,0.08)] border border-[rgba(43,108,246,0.12)] flex items-center justify-center flex-shrink-0"
              >
                <FileTextOutlined class="text-[#2b6cf6]" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-medium text-[#1d1d1f] mb-1">
                  {{ testCase.title || testCase.name || `测试病历${index + 1}` }}
                </div>
                <div
                  v-if="testCase.description"
                  class="text-xs text-[rgba(29,29,31,0.56)] line-clamp-2"
                >
                  {{ testCase.description }}
                </div>
                <div class="mt-2 flex items-center gap-2 text-xs text-[rgba(29,29,31,0.38)]">
                  <ClockCircleOutlined />
                  <span>{{ formatDate(testCase.createdAt) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty state -->
          <div
            v-if="testCases.length === 0"
            class="p-8 text-center text-[rgba(29,29,31,0.38)]"
          >
            <FileTextOutlined class="text-4xl mb-3" />
            <p>暂无测试病历</p>
            <button
              class="mt-3 text-[#2b6cf6] hover:text-[#0057b8] text-sm"
              @click="showCreateModal = true"
            >
              点击创建第一个
            </button>
          </div>
        </div>
      </div>

      <!-- Right: Case Content -->
      <div
        class="flex-1 bg-white/90 rounded-2xl border border-black/[0.08] shadow-[0_1px_4px_rgba(0,0,0,0.045),0_2px_8px_rgba(0,0,0,0.035)] backdrop-blur-[18px] flex flex-col overflow-hidden"
      >
        <div
          v-if="selectedCase"
          class="px-5 py-4 border-b border-black/[0.08] flex items-center justify-between"
        >
          <div>
            <h3 class="text-sm font-semibold text-[#1d1d1f]">
              {{ selectedCase.title || selectedCase.name || `测试病历${selectedIndex + 1}` }}
            </h3>
            <p
              v-if="selectedCase?.description"
              class="text-xs text-[rgba(29,29,31,0.56)] mt-1"
            >
              {{ selectedCase.description }}
            </p>
          </div>
          <div class="flex gap-2">
            <button
              class="px-4 py-2 bg-[#2b6cf6] text-white rounded-lg hover:bg-[#0057b8] transition-colors text-sm flex items-center gap-2 shadow-[0_5px_14px_rgba(43,108,246,0.18)]"
              @click="loadCase"
            >
              <UploadOutlined />
              加载到工作台
            </button>
            <button
              class="px-4 py-2 bg-white text-[rgba(29,29,31,0.7)] border border-black/[0.10] rounded-lg hover:bg-[#f5f5f7] transition-colors text-sm flex items-center gap-2"
              @click="copyContent"
            >
              <CopyOutlined />
              复制内容
            </button>
            <button
              v-if="selectedIndex >= 2"
              class="px-4 py-2 bg-amber-50/70 text-amber-600 border border-amber-100 rounded-lg hover:bg-amber-50 transition-colors text-sm flex items-center gap-2"
              @click="openEditModal"
            >
              <EditOutlined />
              编辑
            </button>
            <button
              v-if="selectedIndex >= 2"
              class="px-4 py-2 bg-red-50/70 text-red-600 border border-red-100 rounded-lg hover:bg-red-50 transition-colors text-sm flex items-center gap-2"
              @click="confirmDelete"
            >
              <DeleteOutlined />
              删除
            </button>
          </div>
        </div>

        <div
          v-if="selectedCase"
          class="flex-1 overflow-y-auto p-5"
        >
          <div class="bg-[#f5f5f7]/75 rounded-lg p-4 border border-black/[0.08]">
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs font-semibold text-[rgba(29,29,31,0.56)]">病历原文</span>
              <span class="text-xs text-[rgba(29,29,31,0.38)]">{{ selectedCase?.medical_text.length }} 字符</span>
            </div>
            <pre
              class="text-sm text-[rgba(29,29,31,0.78)] whitespace-pre-wrap font-mono leading-relaxed"
            >{{ selectedCase?.medical_text }}</pre>
          </div>

          <!-- Metadata -->
          <div class="mt-4 grid grid-cols-2 gap-4">
            <div class="bg-[#f5f5f7]/75 rounded-lg p-4 border border-black/[0.08]">
              <div class="text-xs font-semibold text-[rgba(29,29,31,0.56)] mb-2">
                创建信息
              </div>
              <div class="space-y-2 text-sm">
                <div class="flex justify-between">
                  <span class="text-[rgba(29,29,31,0.56)]">创建时间:</span>
                  <span class="text-[rgba(29,29,31,0.78)]">{{
                    formatDate(selectedCase?.createdAt)
                  }}</span>
                </div>
              </div>
            </div>

            <div class="bg-[#f5f5f7]/75 rounded-lg p-4 border border-black/[0.08]">
              <div class="text-xs font-semibold text-[rgba(29,29,31,0.56)] mb-2">
                统计信息
              </div>
              <div class="space-y-2 text-sm">
                <div class="flex justify-between">
                  <span class="text-[rgba(29,29,31,0.56)]">字符数:</span>
                  <span class="text-[rgba(29,29,31,0.78)]">{{
                    selectedCase?.medical_text.length
                  }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-[rgba(29,29,31,0.56)]">行数:</span>
                  <span class="text-[rgba(29,29,31,0.78)]">{{
                    selectedCase?.medical_text.split('\n').length
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty state for right panel -->
        <div
          v-else
          class="flex-1 flex items-center justify-center text-[rgba(29,29,31,0.38)]"
        >
          <div class="text-center">
            <FileTextOutlined class="text-5xl mb-3" />
            <p>请选择或创建一个测试病历</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <a-modal
      v-model:open="showCreateModal"
      title="创建测试病历"
      :width="720"
      :footer="null"
      :destroy-on-close="true"
    >
      <div class="space-y-4 py-2">
        <div>
          <label class="block text-sm font-medium text-[rgba(29,29,31,0.72)] mb-1.5">
            病历名称 <span class="text-red-500">*</span>
          </label>
          <a-input
            v-model:value="newCase.title"
            placeholder="例如：肺炎合并高血压病历"
            size="large"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-[rgba(29,29,31,0.72)] mb-1.5">
            病历原文 <span class="text-red-500">*</span>
          </label>
          <a-textarea
            v-model:value="newCase.medical_text"
            placeholder="粘贴或输入完整的病历原文内容..."
            :rows="12"
            :show-count="true"
            :maxlength="50000"
          />
        </div>

        <div class="flex justify-end gap-3 pt-2">
          <a-button @click="showCreateModal = false">
            取消
          </a-button>
          <a-button
            type="primary"
            :disabled="!newCase.title || !newCase.medical_text"
            @click="createCase"
          >
            <template #icon>
              <PlusOutlined />
            </template>
            创建病历
          </a-button>
        </div>
      </div>
    </a-modal>

    <!-- Edit Modal -->
    <a-modal
      v-model:open="showEditModal"
      title="编辑测试病历"
      :width="720"
      :footer="null"
      :destroy-on-close="true"
    >
      <div class="space-y-4 py-2">
        <div>
          <label class="block text-sm font-medium text-[rgba(29,29,31,0.72)] mb-1.5">
            病历名称 <span class="text-red-500">*</span>
          </label>
          <a-input
            v-model:value="editCase.title"
            placeholder="例如：肺炎合并高血压病历"
            size="large"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-[rgba(29,29,31,0.72)] mb-1.5">
            病历原文 <span class="text-red-500">*</span>
          </label>
          <a-textarea
            v-model:value="editCase.medical_text"
            placeholder="粘贴或输入完整的病历原文内容..."
            :rows="12"
            :show-count="true"
            :maxlength="50000"
          />
        </div>

        <div class="flex justify-end gap-3 pt-2">
          <a-button @click="showEditModal = false">
            取消
          </a-button>
          <a-button
            type="primary"
            :disabled="!editCase.title || !editCase.medical_text"
            @click="saveEdit"
          >
            <template #icon>
              <EditOutlined />
            </template>
            保存修改
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  UploadOutlined,
  CopyOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  testCases: Array<{
    name?: string
    title?: string
    description?: string
    medical_text: string
    type?: string
    createdAt?: string
  }>
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'loadCase', index: number): void
  (e: 'createCase', data: { title: string; medical_text: string; createdAt: string }): void
  (e: 'updateCase', payload: { index: number; title: string; medical_text: string }): void
  (e: 'deleteCase', index: number): void
}>()

const selectedIndex = ref(0)
const showCreateModal = ref(false)
const showEditModal = ref(false)

const newCase = ref({
  title: '',
  medical_text: '',
})

const editCase = ref({
  title: '',
  medical_text: '',
})

const selectedCase = computed(() => props.testCases[selectedIndex.value])

const formatDate = (date?: string) => {
  if (!date) return '2026-01-05'
  return new Date(date).toLocaleDateString('zh-CN')
}

const loadCase = () => {
  emit('loadCase', selectedIndex.value)
  message.success(`已加载测试病历${selectedIndex.value + 1}到工作台`)
}

const copyContent = async () => {
  const text = selectedCase.value?.medical_text || ''
  if (!text) {
    message.warning('病历内容为空')
    return
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      message.success('病历内容已复制到剪贴板')
      return
    }
  } catch (error) {
    // fallback below
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'absolute'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    if (ok) {
      message.success('病历内容已复制到剪贴板')
    } else {
      message.error('复制失败')
    }
  } catch {
    message.error('复制失败')
  }
}

const openEditModal = () => {
  if (selectedIndex.value < 2) {
    message.warning('测试病历1和测试病历2不可编辑')
    return
  }
  const current = selectedCase.value
  editCase.value = {
    title: current?.title || current?.name || '',
    medical_text: current?.medical_text || '',
  }
  showEditModal.value = true
}

const saveEdit = () => {
  if (!editCase.value.title?.trim()) {
    message.warning('请输入病历名称')
    return
  }
  if (!editCase.value.medical_text?.trim()) {
    message.warning('请输入病历原文')
    return
  }

  emit('updateCase', {
    index: selectedIndex.value,
    title: editCase.value.title.trim(),
    medical_text: editCase.value.medical_text.trim(),
  })
  showEditModal.value = false
  message.success('测试病历已更新')
}

const confirmDelete = () => {
  if (selectedIndex.value < 2) {
    message.warning('测试病历1和测试病历2不可删除')
    return
  }

  const title =
    selectedCase.value?.title || selectedCase.value?.name || `测试病历${selectedIndex.value + 1}`
  Modal.confirm({
    title: '删除测试病历',
    content: `确认删除“${title}”？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => {
      emit('deleteCase', selectedIndex.value)
      message.success('测试病历已删除')
    },
  })
}

const createCase = () => {
  if (!newCase.value.title?.trim()) {
    message.warning('请输入病历名称')
    return
  }
  if (!newCase.value.medical_text?.trim()) {
    message.warning('请输入病历原文')
    return
  }

  emit('createCase', {
    title: newCase.value.title.trim(),
    medical_text: newCase.value.medical_text.trim(),
    createdAt: new Date().toISOString(),
  })

  // Reset form
  newCase.value = {
    title: '',
    medical_text: '',
  }
  showCreateModal.value = false
  message.success('测试病历创建成功')
}

watch(
  () => props.testCases.length,
  (len) => {
    if (len === 0) {
      selectedIndex.value = 0
      return
    }
    if (selectedIndex.value >= len) {
      selectedIndex.value = Math.max(0, len - 1)
    }
  },
)
</script>
