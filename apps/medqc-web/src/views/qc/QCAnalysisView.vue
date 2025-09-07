<template>
  <div class="page-container">
    <div class="page-header">
      <div class="flex items-center gap-4">
        <a-button :icon="h(ArrowLeftOutlined)" @click="goBack">
          返回
        </a-button>
        <h1 class="page-title">AI质控分析</h1>
      </div>
    </div>
    
    <div class="grid grid-cols-12 gap-6">
      <!-- 病历内容 -->
      <div class="col-span-5">
        <a-card title="病历内容" class="h-full">
          <a-textarea
            v-model:value="recordContent"
            placeholder="请输入或粘贴病历内容..."
            :rows="20"
            class="font-mono text-sm"
          />
        </a-card>
      </div>
      
      <!-- 质控分析面板 -->
      <div class="col-span-7">
        <QCAnalysisPanel 
          :record-id="recordId"
          :record-content="recordContent"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import QCAnalysisPanel from '@/components/medical/QCAnalysisPanel.vue'

const router = useRouter()
const route = useRoute()

// 响应式数据
const recordId = ref(route.params.id as string || 'demo-record-1')
const recordContent = ref('')

// 示例病历内容
const sampleRecord = `病案首页
患者姓名：张三    性别：男    年龄：45岁
入院日期：2024-01-15    出院日期：2024-01-22
科室：心内科

主诉：胸闷气短3天

现病史：
患者3天前无明显诱因出现胸闷气短，活动后加重，伴有心慌，无胸痛、晕厥等症状。既往有高血压病史5年，规律服用降压药物。吸烟史20年，每日1包。

体格检查：
T：36.5℃  P：96次/分  R：20次/分  BP：150/90mmHg
心界稍向左扩大，心律齐，心率96次/分，各瓣膜听诊区未闻及明显杂音。
双肺呼吸音清，未闻及干湿性啰音。

辅助检查：
心电图：窦性心律，ST-T改变
胸片：心影稍增大
血常规：WBC 6.2×10⁹/L，RBC 4.5×10¹²/L，Hb 140g/L
肌钙蛋白I：0.15ng/ml（正常<0.04）

入院诊断：
1. 急性心肌梗死？
2. 高血压病3级 极高危

诊疗经过：
入院后完善相关检查，心电图示ST段抬高，结合临床症状及肌钙蛋白升高，诊断急性ST段抬高型心肌梗死。立即给予双联抗血小板、抗凝、调脂稳定斑块等治疗。

出院诊断：
1. 急性ST段抬高型心肌梗死
2. 高血压病3级 极高危

出院医嘱：
1. 低盐低脂饮食
2. 戒烟戒酒
3. 口服阿司匹林100mg qd
4. 口服氯吡格雷75mg qd
5. 口服美托洛尔25mg bid
6. 定期复查`

// 方法
const goBack = () => {
  router.back()
}

// 生命周期
onMounted(() => {
  recordContent.value = sampleRecord
})
</script>

<style scoped>
.page-container {
  @apply p-6;
}
.page-header {
  @apply flex items-center justify-between mb-6;
}
.page-title {
  @apply text-2xl font-bold text-gray-900;
}
</style> 