<template>
  <div class="medical-record-viewer">
    <a-tabs
      v-model:active-key="activeTab"
      type="card"
      size="small"
    >
      <a-tab-pane
        key="admission"
        tab="入院记录"
      >
        <div class="record-content">
          <a-spin :spinning="loading">
            <div
              v-if="recordData.admission_note"
              v-html="highlightText(recordData.admission_note)"
            />
            <a-empty
              v-else
              description="暂无入院记录"
            />
          </a-spin>
        </div>
      </a-tab-pane>
      <a-tab-pane
        key="progress"
        tab="病程记录"
      >
        <div class="record-content">
          <a-spin :spinning="loading">
            <div
              v-if="recordData.progress_note"
              v-html="highlightText(recordData.progress_note)"
            />
            <a-empty
              v-else
              description="暂无病程记录"
            />
          </a-spin>
        </div>
      </a-tab-pane>
      <a-tab-pane
        key="discharge"
        tab="出院记录"
      >
        <div class="record-content">
          <a-spin :spinning="loading">
            <div
              v-if="recordData.discharge_note"
              v-html="highlightText(recordData.discharge_note)"
            />
            <a-empty
              v-else
              description="暂无出院记录"
            />
          </a-spin>
        </div>
      </a-tab-pane>
    </a-tabs>

    <div class="search-bar">
      <a-input-search
        v-model:value="searchText"
        placeholder="搜索病历关键词..."
        size="small"
        @search="onSearch"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  admissionId?: string
  highlightKeywords?: string[]
}>()

const activeTab = ref('admission')
const loading = ref(false)
const searchText = ref('')

// Mock data structure
const recordData = ref({
  admission_note: '',
  progress_note: '',
  discharge_note: ''
})

// Simulated data loading
const loadRecordData = async () => {
  if (!props.admissionId) return
  
  loading.value = true
  try {
    // In a real app, this would fetch from an API
    // reliable mock data for demo
    await new Promise(resolve => setTimeout(resolve, 500))
    
    recordData.value = {
      admission_note: `
        <h3>入院记录</h3>
        <p><strong>主诉：</strong>反复胸闷、气促2年，加重1周。</p>
        <p><strong>现病史：</strong>患者2年前无明显诱因出现胸闷、气促，活动后加重，休息可缓解。1周前受凉后上述症状加重，伴咳嗽、咳痰，为白色泡沫痰，夜间阵发性呼吸困难，遂来我院就诊。</p>
        <p><strong>既往史：</strong>有"高血压病"史10年，最高血压180/100mmHg，长期口服降压药治疗，血压控制尚可。有"2型糖尿病"史5年。</p>
        <p><strong>体格检查：</strong>T 36.5℃，P 88次/分，R 20次/分，BP 130/80mmHg。神志清，精神软，口唇无发绀，颈静脉无充盈。双肺呼吸音粗，双下肺可闻及湿性啰音。心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。腹平软，无压痛及反跳痛，肝脾肋下未及。双下肢度水肿。</p>
        <p><strong>辅助检查：</strong>心电图示：窦性心律，完全性左束支传导阻滞，ST-T改变。心脏彩超示：左室增大，室壁运动减弱，EF 35%。</p>
        <p><strong>初步诊断：</strong>1. 慢性心力衰竭 急性加重 心功能IV级；2. 原发性高血压 3级 很高危；3. 2型糖尿病。</p>
      `,
      progress_note: `
        <h3>首次病程记录</h3>
        <p><strong>2025-01-04 10:00</strong></p>
        <p>患者老年男性，因"反复胸闷、气促2年，加重1周"入院...</p>
        <hr/>
        <h3>日常病程记录</h3>
        <p><strong>2025-01-05 09:00</strong></p>
        <p>患者诉胸闷气促较前稍好转，咳痰减少。查体：双肺湿啰音较前减少。心率80次/分，律齐。血压125/75mmHg。今日查房指示：继续予利尿、扩管、强心等综合治疗，注意监测电解质。</p>
        <hr/>
        <p><strong>2025-01-07 09:00</strong></p>
        <p>患者神志清，精神可，无胸闷气促，无咳嗽咳痰。胃纳可，二便调。查体：双肺呼吸音清，未闻及干湿性啰音。心率76次/分，律齐。双下肢无水肿。复查电解质正常。拟明日出院。</p>
      `,
      discharge_note: `
        <h3>出院记录</h3>
        <p><strong>入院日期：</strong>2025-01-04</p>
        <p><strong>出院日期：</strong>2025-01-08</p>
        <p><strong>入院诊断：</strong>1. 慢性心力衰竭 急性加重 心功能IV级；2. 原发性高血压 3级 很高危；3. 2型糖尿病。</p>
        <p><strong>诊疗经过：</strong>入院后予完善相关检查，予呋塞米利尿，硝酸甘油扩管，地高辛强心，以及控制血压、血糖等对症支持治疗。患者症状好转，予以出院。</p>
        <p><strong>出院诊断：</strong>1. 慢性心力衰竭 心功能III级；2. 原发性高血压 3级 很高危；3. 2型糖尿病。</p>
        <p><strong>出院医嘱：</strong>1. 低盐低脂糖尿病饮食；2. 遵嘱服药，定期监测血压、血糖；3. 心内科门诊随诊，不适随诊。</p>
      `
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// Highlight text based on keywords
const highlightText = (text: string) => {
  if (!text) return ''
  let result = text
  
  // Highlighting specific keywords from props
  if (props.highlightKeywords && props.highlightKeywords.length > 0) {
    props.highlightKeywords.forEach(keyword => {
      if (keyword) {
        const regex = new RegExp(keyword, 'gi')
        result = result.replace(regex, `<span class="highlight-keyword">${keyword}</span>`)
      }
    })
  }
  
  // Highlighting search text
  if (searchText.value) {
    const regex = new RegExp(searchText.value, 'gi')
    result = result.replace(regex, `<span class="highlight-search">${searchText.value}</span>`)
  }
  
  return result
}

const onSearch = () => {
  // Trigger re-render to apply highlighting
}

watch(() => props.admissionId, () => {
  loadRecordData()
}, { immediate: true })

</script>

<style scoped lang="scss">
.medical-record-viewer {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  background: #fff;
  border-right: 1px solid #f0f0f0;

  :deep(.ant-tabs) {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    
    .ant-tabs-content {
      flex: 1;
      height: 100%;
    }
  }

  .record-content {
    height: 100%;
    overflow-y: auto;
    padding: 16px;
    font-size: 14px;
    line-height: 1.6;
    color: #333;
    background-color: #fafafa;
    
    :deep(h3) {
      margin-top: 16px;
      margin-bottom: 8px;
      font-size: 16px;
      font-weight: bold;
      color: #1890ff;
      border-bottom: 1px solid #e8e8e8;
      padding-bottom: 4px;
    }
    
    :deep(p) {
      margin-bottom: 8px;
    }
    
    :deep(.highlight-keyword) {
      background-color: #fff7e6;
      border-bottom: 2px solid #faad14;
      padding: 0 2px;
    }
    
    :deep(.highlight-search) {
      background-color: #ffccc7;
      color: #cf1322;
      padding: 0 2px;
    }
  }

  .search-bar {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 200px;
    z-index: 10;
  }
}
</style>
