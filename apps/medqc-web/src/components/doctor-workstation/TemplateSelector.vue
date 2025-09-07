<template>
  <div class="template-selector-overlay" @click="handleOverlayClick">
    <div class="template-selector-modal" @click.stop>
      <!-- 模态框头部 -->
      <div class="modal-header">
        <h3 class="modal-title">
          <i class="fas fa-file-medical"></i>
          选择病历模板
        </h3>
        <button class="close-btn" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 模板分类标签 -->
      <div class="template-categories">
        <button
          v-for="category in categories"
          :key="category.key"
          class="category-btn"
          :class="{ active: selectedCategory === category.key }"
          @click="selectedCategory = category.key"
        >
          <i :class="category.icon"></i>
          {{ category.name }}
        </button>
      </div>

      <!-- 模板列表 -->
      <div class="template-list">
        <div
          v-for="template in filteredTemplates"
          :key="template.id"
          class="template-item"
          @click="selectTemplate(template)"
        >
          <div class="template-header">
            <div class="template-info">
              <h4 class="template-name">{{ template.template_name }}</h4>
              <div class="template-meta">
                <span class="template-category">{{ getCategoryName(template.category) }}</span>
                <span class="template-date">{{ formatDate(template.updated_at) }}</span>
              </div>
            </div>
            <div class="template-actions">
              <button
                class="preview-btn"
                @click.stop="previewTemplate(template)"
                title="预览模板"
              >
                <i class="fas fa-eye"></i>
              </button>
            </div>
          </div>

          <!-- 模板预览 -->
          <div v-if="previewingTemplate?.id === template.id" class="template-preview">
            <div class="preview-header">
              <span class="preview-title">模板预览：</span>
              <button
                class="close-preview-btn"
                @click="previewingTemplate = null"
                title="关闭预览"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
            <div class="preview-content">
              {{ template.template_content }}
            </div>
            <div class="preview-actions">
              <button
                class="btn btn-primary"
                @click="selectTemplate(template)"
              >
                <i class="fas fa-check"></i>
                使用此模板
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredTemplates.length === 0" class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-file-medical"></i>
        </div>
        <p>该分类下暂无可用模板</p>
      </div>

      <!-- 模态框底部 -->
      <div class="modal-footer">
        <button class="btn btn-secondary" @click="$emit('close')">
          <i class="fas fa-times"></i>
          取消
        </button>
        <button
          class="btn btn-success"
          @click="createCustomTemplate"
          title="创建自定义模板"
        >
          <i class="fas fa-plus"></i>
          创建模板
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { MedicalRecordTemplate } from '@/api/medical-records'

// Props
interface Props {
  templates: MedicalRecordTemplate[]
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  select: [template: MedicalRecordTemplate]
  close: []
}>()

// 响应式数据
const selectedCategory = ref<string>('all')
const previewingTemplate = ref<MedicalRecordTemplate | null>(null)

// 模板分类
const categories = [
  { key: 'all', name: '全部', icon: 'fas fa-list' },
  { key: 'admission', name: '入院记录', icon: 'fas fa-sign-in-alt' },
  { key: 'discharge', name: '出院记录', icon: 'fas fa-sign-out-alt' },
  { key: 'progress', name: '病程记录', icon: 'fas fa-notes-medical' },
  { key: 'consultation', name: '会诊记录', icon: 'fas fa-users' },
  { key: 'operation', name: '手术记录', icon: 'fas fa-cut' },
  { key: 'examination', name: '检查记录', icon: 'fas fa-stethoscope' }
]

// 计算属性
const filteredTemplates = computed(() => {
  if (selectedCategory.value === 'all') {
    return props.templates
  }
  return props.templates.filter(template => template.category === selectedCategory.value)
})

// 方法
const getCategoryName = (category: string): string => {
  const categoryMap: Record<string, string> = {
    admission: '入院记录',
    discharge: '出院记录',
    progress: '病程记录',
    consultation: '会诊记录',
    operation: '手术记录',
    examination: '检查记录'
  }
  return categoryMap[category] || category
}

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('zh-CN')
}

const handleOverlayClick = () => {
  // 点击遮罩层关闭模态框
  emit('close')
}

const selectTemplate = (template: MedicalRecordTemplate) => {
  emit('select', template)
}

const previewTemplate = (template: MedicalRecordTemplate) => {
  previewingTemplate.value = previewingTemplate.value?.id === template.id ? null : template
}

const createCustomTemplate = () => {
  // 这里可以打开创建自定义模板的对话框
  console.log('创建自定义模板')
}
</script>

<style scoped>
.template-selector-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.template-selector-modal {
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e1e8ed;
  background: #f8f9fa;
}

.modal-title {
  margin: 0;
  color: #495057;
  font-size: 1.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.close-btn {
  padding: 0.5rem;
  border: none;
  background: none;
  color: #6c757d;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #e9ecef;
  color: #495057;
}

.template-categories {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
  border-bottom: 1px solid #e1e8ed;
  background: white;
  overflow-x: auto;
}

.category-btn {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  background: white;
  color: #6c757d;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.875rem;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}

.category-btn:hover {
  background: #f8f9fa;
  border-color: #adb5bd;
}

.category-btn.active {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.template-list {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.template-item {
  border: 1px solid #e1e8ed;
  border-radius: 6px;
  margin-bottom: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}

.template-item:hover {
  border-color: #007bff;
  box-shadow: 0 2px 8px rgba(0, 123, 255, 0.15);
}

.template-item:last-child {
  margin-bottom: 0;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: white;
}

.template-info {
  flex: 1;
}

.template-name {
  margin: 0 0 0.5rem 0;
  color: #495057;
  font-size: 1rem;
}

.template-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  color: #6c757d;
}

.template-actions {
  display: flex;
  gap: 0.5rem;
}

.preview-btn {
  padding: 0.5rem;
  border: 1px solid #ddd;
  background: white;
  color: #6c757d;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.preview-btn:hover {
  background: #f8f9fa;
  color: #495057;
  border-color: #adb5bd;
}

.template-preview {
  border-top: 1px solid #e1e8ed;
  background: #f8f9fa;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e1e8ed;
  background: #e9ecef;
}

.preview-title {
  font-weight: 500;
  color: #495057;
  font-size: 0.875rem;
}

.close-preview-btn {
  padding: 0.25rem;
  border: none;
  background: none;
  color: #6c757d;
  cursor: pointer;
  border-radius: 3px;
  transition: all 0.2s;
}

.close-preview-btn:hover {
  background: #dee2e6;
  color: #495057;
}

.preview-content {
  padding: 1rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  color: #495057;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  background: white;
}

.preview-actions {
  padding: 0.75rem 1rem;
  text-align: right;
  background: #f8f9fa;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
  color: #6c757d;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e1e8ed;
  background: #f8f9fa;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #545b62;
}

.btn-success {
  background: #28a745;
  color: white;
}

.btn-success:hover {
  background: #1e7e34;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover {
  background: #0056b3;
}
</style>
