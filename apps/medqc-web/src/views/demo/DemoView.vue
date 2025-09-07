<template>
  <div class="demo-view">
    <!-- 演示页面头部 -->
    <div class="demo-header">
      <div class="demo-title">
        <h1>
          <i class="fas fa-stethoscope"></i>
          医疗质控系统 - 医生工作站演示
        </h1>
        <p class="demo-subtitle">
          体验智能化的病历编辑和实时质控分析功能
        </p>
      </div>
      
      <div class="demo-actions">
        <button class="demo-btn primary" @click="startDemo">
          <i class="fas fa-play"></i>
          开始演示
        </button>
        <button class="demo-btn secondary" @click="showFeatures = !showFeatures">
          <i class="fas fa-info-circle"></i>
          功能介绍
        </button>
      </div>
    </div>

    <!-- 功能介绍面板 -->
    <div v-if="showFeatures" class="features-panel">
      <div class="features-container">
        <h2>
          <i class="fas fa-star"></i>
          核心功能特性
        </h2>
        
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-edit"></i>
            </div>
            <h3>智能病历编辑</h3>
            <p>支持富文本编辑、模板快速插入、自动保存草稿等功能，提升医生录入效率</p>
            <ul>
              <li>富文本编辑器</li>
              <li>病历模板库</li>
              <li>自动保存草稿</li>
              <li>快捷键支持</li>
            </ul>
          </div>

          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-shield-alt"></i>
            </div>
            <h3>实时质控分析</h3>
            <p>基于AI算法的实时质控分析，在医生编辑过程中提供即时反馈和改进建议</p>
            <ul>
              <li>实时质控检查</li>
              <li>智能评分系统</li>
              <li>问题定位提示</li>
              <li>改进建议推荐</li>
            </ul>
          </div>

          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-chart-line"></i>
            </div>
            <h3>质控结果可视化</h3>
            <p>直观的质控结果展示，包括评分仪表盘、问题分类统计、改进趋势分析</p>
            <ul>
              <li>评分仪表盘</li>
              <li>问题分类展示</li>
              <li>改进建议列表</li>
              <li>历史趋势分析</li>
            </ul>
          </div>

          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-cogs"></i>
            </div>
            <h3>多场景演示</h3>
            <p>提供多种病历场景演示，展示不同质控问题的识别和处理效果</p>
            <ul>
              <li>完整病历场景</li>
              <li>不完整病历场景</li>
              <li>数据不一致场景</li>
              <li>诊断不合理场景</li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- 演示场景选择 -->
    <div v-if="!demoStarted" class="scenario-selection">
      <div class="scenario-container">
        <h2>
          <i class="fas fa-play-circle"></i>
          选择演示场景
        </h2>
        
        <div class="scenarios-grid">
          <div
            v-for="scenario in scenarios"
            :key="scenario.key"
            class="scenario-card"
            @click="selectScenario(scenario.key)"
          >
            <div class="scenario-icon" :class="scenario.iconClass">
              <i :class="scenario.icon"></i>
            </div>
            <h3>{{ scenario.name }}</h3>
            <p>{{ scenario.description }}</p>
            <div class="scenario-features">
              <span
                v-for="feature in scenario.features"
                :key="feature"
                class="feature-tag"
              >
                {{ feature }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 医生工作站演示 -->
    <div v-if="demoStarted" class="workstation-demo">
      <div class="demo-controls">
        <button class="control-btn" @click="resetDemo">
          <i class="fas fa-undo"></i>
          重新开始
        </button>
        <button class="control-btn" @click="switchScenario">
          <i class="fas fa-exchange-alt"></i>
          切换场景
        </button>
        <button class="control-btn" @click="showHelp = !showHelp">
          <i class="fas fa-question-circle"></i>
          操作帮助
        </button>
      </div>

      <!-- 操作帮助提示 -->
      <div v-if="showHelp" class="help-panel">
        <div class="help-content">
          <h3>
            <i class="fas fa-lightbulb"></i>
            操作提示
          </h3>
          <div class="help-steps">
            <div class="help-step">
              <span class="step-number">1</span>
              <div class="step-content">
                <strong>编辑病历：</strong>在左侧编辑器中输入或修改病历内容
              </div>
            </div>
            <div class="help-step">
              <span class="step-number">2</span>
              <div class="step-content">
                <strong>实时分析：</strong>点击"质控分析"按钮查看实时质控结果
              </div>
            </div>
            <div class="help-step">
              <span class="step-number">3</span>
              <div class="step-content">
                <strong>查看建议：</strong>在右侧面板查看质控评分和改进建议
              </div>
            </div>
            <div class="help-step">
              <span class="step-number">4</span>
              <div class="step-content">
                <strong>应用建议：</strong>点击建议旁的按钮快速应用改进建议
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 工作站组件 -->
      <DoctorWorkstation />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DoctorWorkstation from '@/components/doctor-workstation/DoctorWorkstation.vue'

// 响应式数据
const showFeatures = ref(false)
const demoStarted = ref(false)
const showHelp = ref(false)
const selectedScenario = ref<string>('')

// 演示场景配置
const scenarios = [
  {
    key: 'complete',
    name: '完整病历演示',
    description: '展示标准完整病历的质控分析效果，演示高质量病历的评分结果',
    icon: 'fas fa-check-circle',
    iconClass: 'success',
    features: ['高质量评分', '完整性检查', '标准化格式']
  },
  {
    key: 'incomplete',
    name: '不完整病历演示',
    description: '展示不完整病历的质控问题识别，演示系统如何发现缺失信息',
    icon: 'fas fa-exclamation-triangle',
    iconClass: 'warning',
    features: ['缺失信息提示', '完整性建议', '补充指导']
  },
  {
    key: 'inconsistent',
    name: '数据不一致演示',
    description: '展示数据前后不一致的质控检查，演示逻辑一致性验证功能',
    icon: 'fas fa-times-circle',
    iconClass: 'error',
    features: ['一致性检查', '逻辑验证', '冲突提示']
  },
  {
    key: 'irrational',
    name: '诊断不合理演示',
    description: '展示诊断与症状不匹配的质控分析，演示合理性判断功能',
    icon: 'fas fa-brain',
    iconClass: 'info',
    features: ['合理性分析', '诊断建议', '专业指导']
  }
]

// 方法
const startDemo = () => {
  if (!selectedScenario.value) {
    // 如果没有选择场景，显示场景选择
    return
  }
  demoStarted.value = true
  showFeatures.value = false
}

const selectScenario = (scenarioKey: string) => {
  selectedScenario.value = scenarioKey
  demoStarted.value = true
  showFeatures.value = false
}

const resetDemo = () => {
  demoStarted.value = false
  selectedScenario.value = ''
  showHelp.value = false
}

const switchScenario = () => {
  demoStarted.value = false
  showHelp.value = false
}
</script>

<style scoped>
.demo-view {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.demo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2rem;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.demo-title h1 {
  margin: 0 0 0.5rem 0;
  color: white;
  font-size: 2rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.demo-subtitle {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
  font-size: 1.1rem;
}

.demo-actions {
  display: flex;
  gap: 1rem;
}

.demo-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.3s;
  font-weight: 500;
}

.demo-btn.primary {
  background: #28a745;
  color: white;
}

.demo-btn.primary:hover {
  background: #218838;
  transform: translateY(-2px);
}

.demo-btn.secondary {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.demo-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

.features-panel {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.features-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 3rem 2rem;
}

.features-container h2 {
  text-align: center;
  margin-bottom: 3rem;
  color: #333;
  font-size: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
}

.feature-card {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s;
}

.feature-card:hover {
  transform: translateY(-5px);
}

.feature-icon {
  width: 60px;
  height: 60px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
  font-size: 1.5rem;
  color: white;
}

.feature-card h3 {
  margin: 0 0 1rem 0;
  color: #333;
  font-size: 1.25rem;
}

.feature-card p {
  margin: 0 0 1.5rem 0;
  color: #666;
  line-height: 1.6;
}

.feature-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.feature-card li {
  padding: 0.5rem 0;
  color: #555;
  position: relative;
  padding-left: 1.5rem;
}

.feature-card li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #28a745;
  font-weight: bold;
}

.scenario-selection {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  min-height: calc(100vh - 120px);
  padding: 3rem 2rem;
}

.scenario-container {
  max-width: 1200px;
  margin: 0 auto;
}

.scenario-container h2 {
  text-align: center;
  margin-bottom: 3rem;
  color: #333;
  font-size: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
}

.scenarios-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
}

.scenario-card {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.scenario-card:hover {
  transform: translateY(-5px);
  border-color: #667eea;
}

.scenario-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1.5rem;
  font-size: 2rem;
  color: white;
}

.scenario-icon.success {
  background: linear-gradient(135deg, #28a745, #20c997);
}

.scenario-icon.warning {
  background: linear-gradient(135deg, #ffc107, #fd7e14);
}

.scenario-icon.error {
  background: linear-gradient(135deg, #dc3545, #e83e8c);
}

.scenario-icon.info {
  background: linear-gradient(135deg, #17a2b8, #6f42c1);
}

.scenario-card h3 {
  text-align: center;
  margin: 0 0 1rem 0;
  color: #333;
  font-size: 1.25rem;
}

.scenario-card p {
  text-align: center;
  margin: 0 0 1.5rem 0;
  color: #666;
  line-height: 1.6;
}

.scenario-features {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.feature-tag {
  padding: 0.25rem 0.75rem;
  background: #f8f9fa;
  color: #495057;
  border-radius: 20px;
  font-size: 0.875rem;
  border: 1px solid #e9ecef;
}

.workstation-demo {
  background: white;
  min-height: 100vh;
}

.demo-controls {
  display: flex;
  gap: 1rem;
  padding: 1rem 2rem;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.control-btn {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  background: white;
  color: #495057;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}

.control-btn:hover {
  background: #e9ecef;
  border-color: #adb5bd;
}

.help-panel {
  background: #e7f3ff;
  border-bottom: 1px solid #b3d9ff;
  padding: 1.5rem 2rem;
}

.help-content h3 {
  margin: 0 0 1.5rem 0;
  color: #0056b3;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.help-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.help-step {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.step-number {
  width: 24px;
  height: 24px;
  background: #007bff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: bold;
  flex-shrink: 0;
}

.step-content {
  color: #495057;
  font-size: 0.875rem;
  line-height: 1.5;
}

.step-content strong {
  color: #0056b3;
}
</style>
