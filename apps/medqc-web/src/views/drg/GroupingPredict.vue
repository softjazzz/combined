<template>
  <div class="grouping-predict">
    <a-page-header
      title="DRG 分组预测"
      sub-title="DRG 入组预测和费用分析"
      @back="() => $router.back()"
    />

    <div class="content-wrapper">
      <a-row :gutter="16">
        <!-- 左侧：病案选择 -->
        <a-col :span="8">
          <a-card title="选择病案" :bordered="false">
            <a-select
              v-model:value="selectedAdmissionId"
              show-search
              placeholder="选择或搜索病案"
              style="width: 100%"
              @change="handleSelectCase"
            >
              <a-select-option v-for="item in caseFrontPages" :key="item.admission_id" :value="item.admission_id">
                {{ item.admission_id }} - {{ item.patient_name }}
              </a-select-option>
            </a-select>

            <a-divider />

            <a-button
              type="primary"
              block
              :loading="predicting"
              :disabled="!selectedAdmissionId"
              @click="handlePredict"
            >
              <template #icon><ThunderboltOutlined /></template>
              预测分组
            </a-button>
          </a-card>
        </a-col>

        <!-- 右侧：分组结果 -->
        <a-col :span="16">
          <a-card title="分组结果" :bordered="false" v-if="groupingResult">
            <a-descriptions bordered :column="2">
              <a-descriptions-item label="ADRG">
                <a-tag color="blue" style="font-size: 16px">{{ groupingResult.adrg_code }}</a-tag>
                <span>{{ groupingResult.adrg_name }}</span>
              </a-descriptions-item>
              <a-descriptions-item label="DRG">
                <a-tag color="green" style="font-size: 16px">{{ groupingResult.drg_code }}</a-tag>
                <span>{{ groupingResult.drg_name }}</span>
              </a-descriptions-item>
              <a-descriptions-item label="DRG 权重">
                <a-statistic :value="groupingResult.weight" :precision="4" />
              </a-descriptions-item>
              <a-descriptions-item label="基准支付金额">
                <a-statistic
                  :value="groupingResult.baseline_payment"
                  prefix="¥"
                  :precision="2"
                  style="color: #cf1322"
                />
              </a-descriptions-item>
              <a-descriptions-item label="预期住院日" v-if="groupingResult.expected_los">
                {{ groupingResult.expected_los.min }} - {{ groupingResult.expected_los.max }} 天
              </a-descriptions-item>
              <a-descriptions-item label="风险等级" v-if="groupingResult.risk_level">
                <StatusTag type="risk" :value="groupingResult.risk_level" />
              </a-descriptions-item>
              <a-descriptions-item label="分组置信度" v-if="groupingResult.confidence" :span="2">
                <a-progress :percent="Math.round(groupingResult.confidence * 100)" />
              </a-descriptions-item>
              <a-descriptions-item label="分组逻辑" :span="2" v-if="groupingResult.grouping_logic">
                <a-typography-paragraph>
                  {{ groupingResult.grouping_logic }}
                </a-typography-paragraph>
              </a-descriptions-item>
            </a-descriptions>
          </a-card>
          <a-empty v-else description="请选择病案并进行分组预测" />
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ThunderboltOutlined } from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import type { CaseFrontPage, DRGGroupingResult } from '@/types/drg'

const caseFrontPages = ref<CaseFrontPage[]>([])
const selectedAdmissionId = ref<string>()
const groupingResult = ref<DRGGroupingResult>()
const predicting = ref(false)

/** 加载病案列表 */
const loadCaseFrontPages = async () => {
  try {
    const data = await drgApi.getCaseFrontPages()
    caseFrontPages.value = data
  } catch (error) {
    console.error('加载病案列表失败:', error)
  }
}

/** 选择病案 */
const handleSelectCase = () => {
  groupingResult.value = undefined
}

/** 预测分组 */
const handlePredict = async () => {
  if (!selectedAdmissionId.value) {
    return
  }

  predicting.value = true
  try {
    const response = await drgApi.predictDRGGrouping({
      admission_id: selectedAdmissionId.value,
      region: 'sichuan'
    })
    groupingResult.value = response.data
    message.success('分组预测完成')
  } catch (error) {
    console.error('分组预测失败:', error)
    message.error('分组预测失败')
  } finally {
    predicting.value = false
  }
}

onMounted(() => {
  loadCaseFrontPages()
})
</script>

<style scoped lang="scss">
.grouping-predict {
  .content-wrapper {
    padding: 16px;
  }
}
</style>
