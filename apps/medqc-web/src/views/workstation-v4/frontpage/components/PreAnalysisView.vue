<template>
  <div class="pre-analysis-shell drg-workbench-page">
    <section class="command-header mq-card">
      <div class="command-top mq-page-head">
        <div class="title-block mq-page-head__copy">
          <span class="eyebrow mq-page-eyebrow">分析 · DRG/DIP</span>
          <h1 class="mq-page-title">事前分析</h1>
          <p>只读完成病历字段抽取、编码核对与模拟入组，不写正式结果。</p>
        </div>

        <div class="header-tools mq-page-head__actions">
          <span class="readonly-badge">只读模拟</span>
          <span class="stage-badge">{{ currentStageLabel }}</span>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="extracting || grouping"
            @click="handleExtract"
          >
            {{ extracting ? '抽取中...' : '执行抽取' }}
          </button>
          <div class="segmented mq-segmented" role="tablist" aria-label="分组类型">
            <button
              type="button"
              class="segmented-item mq-segmented__item"
              :class="{ active: groupingType === 'DIP' }"
              :disabled="extracting || grouping || !hasExtractedData"
              @click="handleDIPGrouping"
            >
              DIP
            </button>
            <button
              type="button"
              class="segmented-item mq-segmented__item"
              :class="{ active: groupingType === 'DRG' }"
              :disabled="extracting || grouping || !hasExtractedData"
              @click="handleDRGGrouping"
            >
              DRG
            </button>
          </div>
        </div>
      </div>

      <div class="pre-analysis-filter-strip">
        <div class="case-selector">
          <span class="filter-label">病案选择</span>
          <button
            v-for="(item, index) in testCases"
            :key="item.name"
            type="button"
            class="case-pill"
            :class="{ active: selectedCaseIndex === index }"
            @click="handleCaseChange(index)"
          >
            <span>{{ item.admissionId || `病案 ${index + 1}` }}</span>
            <strong>{{ item.name }}</strong>
          </button>
        </div>
        <div class="current-case">
          <span>当前病案</span>
          <strong>{{ currentCase.admissionId }}</strong>
          <em>{{ currentCase.name }}</em>
        </div>
      </div>

      <div class="command-metrics">
        <div class="metric-inline metric-inline--active">
          <span>状态</span>
          <strong>{{ currentStageLabel }}</strong>
        </div>
        <div class="metric-inline">
          <span>文书</span>
          <strong>{{ textLength }}</strong>
          <em>字</em>
        </div>
        <div class="metric-inline">
          <span>诊断</span>
          <strong>{{ diagnosisCount }}</strong>
          <em>条</em>
        </div>
        <div class="metric-inline">
          <span>手术</span>
          <strong>{{ procedures.length }}</strong>
          <em>条</em>
        </div>
      </div>
    </section>

    <section class="analysis-layout">
      <aside class="side-rail surface mq-card">
        <div class="panel-head">
          <div>
            <h2>病例队列</h2>
            <p>选择病历后重新抽取与预判</p>
          </div>
        </div>

        <div class="case-list" role="tablist" aria-label="病例切换">
          <button
            v-for="(item, index) in testCases"
            :key="item.name"
            type="button"
            class="case-chip"
            :class="{ active: selectedCaseIndex === index }"
            @click="handleCaseChange(index)"
          >
            <span class="case-chip__id">{{ item.admissionId || `病例 ${index + 1}` }}</span>
            <strong>{{ item.name }}</strong>
          </button>
        </div>

        <div class="case-metrics">
          <div class="case-metric">
            <span>文书</span>
            <strong>{{ textLength }}</strong>
            <small>字</small>
          </div>
          <div class="case-metric">
            <span>诊断</span>
            <strong>{{ diagnosisCount }}</strong>
            <small>条</small>
          </div>
          <div class="case-metric">
            <span>手术</span>
            <strong>{{ procedures.length }}</strong>
            <small>条</small>
          </div>
        </div>

        <div class="workflow-block">
          <h3>分析流程</h3>
          <div class="workflow-node" :class="{ active: !!medicalText }">
            <span class="workflow-node__index">01</span>
            <div>
              <div class="workflow-node__title">病历阅读</div>
              <div class="workflow-node__desc">确认原始文本与临床场景</div>
            </div>
          </div>
          <div class="workflow-node" :class="{ active: hasExtractedData }">
            <span class="workflow-node__index">02</span>
            <div>
              <div class="workflow-node__title">结构化抽取</div>
              <div class="workflow-node__desc">沉淀主诊断、手术与费用字段</div>
            </div>
          </div>
          <div class="workflow-node" :class="{ active: !!drgResult }">
            <span class="workflow-node__index">03</span>
            <div>
              <div class="workflow-node__title">分组预判</div>
              <div class="workflow-node__desc">输出模拟结果与费用判断</div>
            </div>
          </div>
        </div>

        <div class="safety-note">
          <span>安全边界</span>
          <strong>不写病案首页、医保结算清单或正式 DRG/DIP 结果。</strong>
        </div>
      </aside>

      <article class="surface mq-card reader-panel">
        <div class="panel-head panel-head--between">
          <div>
            <h2>原始病历内容</h2>
            <p>支持直接粘贴或编辑病历，执行抽取后生成高亮预览</p>
          </div>
          <div class="reading-meta">
            <span>当前病案</span>
            <strong>{{ currentCase.admissionId }}</strong>
            <span>{{ currentCase.name }}</span>
          </div>
        </div>

        <div class="reader-body">
          <div class="medical-editor-wrap">
            <textarea
              v-model="medicalText"
              class="medical-text-editor"
              :disabled="extracting || grouping"
              spellcheck="false"
              placeholder="请粘贴完整入院记录、病程记录、手术记录或出院小结等病历文本..."
              @input="handleMedicalTextEdited"
            />
          </div>

          <div class="reader-preview">
            <div class="reader-preview__head">
              <span>抽取高亮预览</span>
              <em>{{
                hasExtractedData ? '已根据抽取结果高亮' : '执行抽取后显示诊断和手术高亮'
              }}</em>
            </div>
            <div class="reader-scroll">
              <div class="medical-text">
                <template
                  v-for="(seg, segIdx) in highlightedMedicalTextSegments"
                  :key="segIdx"
                >
                  <br v-if="seg.type === 'br'">
                  <mark
                    v-else-if="seg.type === 'diag'"
                    class="hl-diag"
                  >{{ seg.text }}</mark>
                  <mark
                    v-else-if="seg.type === 'proc'"
                    class="hl-proc"
                  >{{ seg.text }}</mark>
                  <template v-else>{{ seg.text }}</template>
                </template>
              </div>
            </div>
          </div>
        </div>
      </article>

      <aside class="result-column">
        <article class="surface mq-card result-card">
          <div class="panel-head panel-head--between">
            <div>
              <h2>抽取结果</h2>
              <p>主诊断、手术和候选编码</p>
            </div>
            <span class="status-pill">{{ hasExtractedData ? '已抽取' : '待抽取' }}</span>
          </div>

          <div class="summary-list">
            <div class="summary-row">
              <span class="summary-row__label">主诊断</span>
              <strong>{{
                hasExtractedData && mainDiagnosis
                  ? mainDiagnosis.text || mainDiagnosis.code || '已抽取'
                  : '等待抽取'
              }}</strong>
              <span class="summary-row__meta">编码 {{ mainDiagnosis?.code || '--' }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-row__label">手术 / 操作</span>
              <strong>{{ procedures.length ? procedures[0].text || '已抽取' : '等待抽取' }}</strong>
              <span class="summary-row__meta">{{
                hasExtractedData ? `${procedures.length} 条` : '0 条'
              }}</span>
            </div>
          </div>

          <div v-if="secondaryDiagnoses.length" class="tag-block">
            <span class="tag-block__label">次诊断</span>
            <div class="tag-list">
              <span
                v-for="(item, idx) in secondaryDiagnoses.slice(0, 5)"
                :key="`${item.code || item.text}-${idx}`"
                class="tag-item"
              >
                {{ item.text || item.code || '未命名诊断' }}
              </span>
            </div>
          </div>

          <div
            v-if="latestPreGroupingSimulation"
            class="simulation-version"
            data-testid="pre-grouping-version"
          >
            <div class="simulation-version__head">
              <span>自动模拟版本</span>
              <strong>V{{ latestPreGroupingSimulation.version }}</strong>
              <em>{{ formatSimulationTime(latestPreGroupingSimulation.created_at) }}</em>
            </div>
            <div class="simulation-version__body">
              <span>{{
                latestPreGroupingSimulation.change_tracking?.needs_regrouping
                  ? '检测到输入变化'
                  : '关键输入未变化'
              }}</span>
              <div v-if="preGroupingChangedFields.length" class="simulation-version__changes">
                <span v-for="item in preGroupingChangedFields.slice(0, 4)" :key="item.field">
                  {{ preGroupingFieldLabel(item.field) }}
                </span>
              </div>
            </div>
          </div>
        </article>

        <article class="surface mq-card result-card">
          <div class="panel-head panel-head--between">
            <div>
              <h2>预判结果</h2>
              <p>模拟入组，不写正式结果</p>
            </div>
            <div
              class="segmented mq-segmented segmented--compact"
              role="tablist"
              aria-label="分组类型"
            >
              <button
                type="button"
                class="segmented-item mq-segmented__item"
                :class="{ active: groupingType === 'DIP' }"
                :disabled="extracting || grouping || !hasExtractedData"
                @click="handleDIPGrouping"
              >
                DIP
              </button>
              <button
                type="button"
                class="segmented-item mq-segmented__item"
                :class="{ active: groupingType === 'DRG' }"
                :disabled="extracting || grouping || !hasExtractedData"
                @click="handleDRGGrouping"
              >
                DRG
              </button>
            </div>
          </div>

          <div v-if="drgResult" class="group-result">
            <div class="group-result__top">
              <span class="group-badge">{{ drgResult.groupingType || groupingType }}</span>
              <h3>{{ drgResult.groupName || drgResult.name || '未返回分组' }}</h3>
              <p>{{ drgResult.message || '分组结果已生成，可继续核对费用结构与手术匹配。' }}</p>
            </div>

            <div class="metric-grid">
              <div class="metric-card mq-card">
                <span>权重 / 点数</span>
                <strong>{{ drgResult.weight || '--' }}</strong>
              </div>
              <template v-if="drgResult.groupingType === 'DRG'">
                <div class="metric-card mq-card">
                  <span>低风险组</span>
                  <strong>{{
                    drgResult.isLowRisk === undefined ? '--' : drgResult.isLowRisk ? '是' : '否'
                  }}</strong>
                </div>
                <div class="metric-card mq-card">
                  <span>权重来源</span>
                  <strong>{{ drgResult.weightSource ? '2024绩效监测权重' : '--' }}</strong>
                </div>
              </template>
              <div class="metric-card mq-card">
                <span>预估费用</span>
                <strong>{{
                  drgResult.payment !== '--' ? drgResult.payment?.toLocaleString() : '--'
                }}</strong>
              </div>
              <div class="metric-card mq-card">
                <span>实际费用</span>
                <strong>{{
                  drgResult.actual_cost !== '--' ? drgResult.actual_cost?.toLocaleString() : '--'
                }}</strong>
              </div>
              <div class="metric-card mq-card">
                <span>盈亏情况</span>
                <strong :class="profitClass">{{
                  drgResult.profit !== '--' ? drgResult.profit?.toLocaleString() : '--'
                }}</strong>
              </div>
              <template v-if="drgResult.groupingType === 'DIP'">
                <div class="metric-card mq-card">
                  <span>分值</span>
                  <strong>{{ drgResult.score ?? '--' }}</strong>
                </div>
                <div class="metric-card mq-card">
                  <span>病种属性</span>
                  <strong>{{ drgResult.diseaseAttribute || '--' }}</strong>
                </div>
                <div class="metric-card mq-card">
                  <span>基层病种标识</span>
                  <strong>{{ drgResult.primaryCareFlag || '否' }}</strong>
                </div>
              </template>
            </div>

            <div v-if="groupingCorrections" class="correction-panel">
              <div class="correction-panel__head">
                <span>修正建议</span>
                <em>{{ groupingCorrections.suggestions.length }} 条</em>
              </div>
              <div v-if="groupingCorrections.suggestions.length" class="correction-list">
                <div
                  v-for="item in groupingCorrections.suggestions.slice(0, 3)"
                  :key="`${item.suggestion_type}-${item.title}`"
                  class="correction-item"
                >
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.reason }}</p>
                  <div v-if="item.candidates?.length" class="correction-candidates">
                    <span
                      v-for="candidate in item.candidates.slice(0, 3)"
                      :key="candidate.code || candidate.name"
                    >
                      {{ candidate.code || '--' }} {{ candidate.name || candidate.dip_name || '' }}
                    </span>
                  </div>
                </div>
              </div>
              <div v-else class="correction-empty">当前分组未返回需要调整的编码建议。</div>
              <p class="correction-warning">
                {{ groupingCorrections.safety_warning }}
              </p>
            </div>

            <div v-if="correctionsLoading && !groupingCorrections" class="correction-empty">
              正在生成预入组修正建议...
            </div>
          </div>

          <div v-else class="empty-state">
            <div class="empty-state__icon">
              {{ groupingType }}
            </div>
            <div class="empty-state__title">等待分组结果</div>
            <div class="empty-state__desc">完成抽取后可生成 DRG / DIP 结果与费用建议。</div>
          </div>
        </article>

        <article class="surface mq-card result-card trace-card">
          <div class="panel-head">
            <div>
              <h2>执行轨迹</h2>
              <p>保留可复核的分组路径</p>
            </div>
          </div>
          <div v-if="drgResult && (drgResult.messages || []).length" class="trace-list">
            <div v-for="(item, idx) in drgResult.messages || []" :key="idx" class="trace-item">
              <div class="trace-item__title">步骤 {{ idx + 1 }}</div>
              <div class="trace-item__value">
                <template
                  v-for="(seg, segIdx) in splitTraceCodeSegments(item)"
                  :key="segIdx"
                >
                  <code
                    v-if="seg.isCode"
                    class="trace-code"
                  >{{ seg.text }}</code>
                  <template v-else>{{ seg.text }}</template>
                </template>
              </div>
            </div>
          </div>
          <div v-else class="trace-empty">暂无轨迹，执行 DRG/DIP 后自动记录。</div>
        </article>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { performGrouping as localDrgGrouping } from '@/views/drg-grouper/drgGrouper'
import { performDipGrouping as localDipGrouping } from '@/views/drg-grouper/dipGrouper'
import { searchICD9Procedures } from '@/data/drg/mock-icd-codes'
import { getAccessToken } from '@/utils/auth-token'
import {
  getPreGroupingHistory,
  suggestGroupingCorrections,
  triggerAdmissionPreGrouping,
  type GroupingCorrectionResult,
  type PreGroupingSimulation,
} from '@/api/drg'

const testCases = [
  {
    name: '冠心病合并高血压',
    admissionId: 'ZS-001',
    medical_text: `入院记录

患者张三，男，58岁，因“反复胸闷、胸痛1年，加重3天”入院。
主诉：反复活动后胸闷、胸痛1年，加重伴夜间憋醒3天。
现病史：患者1年前开始出现快步行走、上楼后胸闷、胸骨后压榨样疼痛，持续约5至10分钟，休息后可缓解，未系统诊治。近1周劳累后症状较前频繁，3天前夜间出现阵发性呼吸困难，伴心悸、出汗，无明显咳嗽咳痰，无咯血，无晕厥。当地门诊心电图提示ST-T改变，予硝酸酯类药物后胸痛缓解不明显，为进一步诊治收入院。入院时神志清楚，精神稍差，平卧后胸闷加重，双下肢无明显水肿。
既往史：高血压病史10年，最高血压约180/100mmHg，长期口服氨氯地平、缬沙坦控制，平素血压波动在140/90mmHg左右；否认糖尿病、脑卒中及慢性肾病史；吸烟30年，每日约20支，偶有饮酒。否认药物及食物过敏史。家族中父亲有冠心病史。
体格检查：T 36.5℃，P 86次/分，R 20次/分，BP 158/92mmHg。双肺呼吸音清，未闻及明显干湿啰音；心率86次/分，律齐，心音低钝，未闻及明显病理性杂音；腹软，无压痛。入院后完善心肌酶、肌钙蛋白、心脏彩超及冠脉CTA检查，提示冠状动脉多支病变可能，左室舒张功能减低。
入院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 心功能不全
3. 高血压病3级（极高危组）
诊疗计划：予心电监护、抗血小板、调脂稳定斑块、控制血压、改善心功能等治疗，评估冠脉介入指征，完善术前谈话及相关检查。
手术情况：2026年1月2日行冠状动脉造影术及支架植入术。术中见前降支近中段重度狭窄，植入药物洗脱支架1枚，术后生命体征平稳。`,
  },
  {
    name: '急性阑尾炎手术',
    admissionId: 'LS-002',
    medical_text: `入院记录

患者李四，男，32岁，因“转移性右下腹痛6小时”入院。
主诉：转移性右下腹痛6小时，伴恶心、低热。
现病史：患者6小时前无明显诱因出现脐周及上腹部隐痛，呈持续性阵发性加重，约2小时后疼痛逐渐转移并固定于右下腹，活动、咳嗽及改变体位时疼痛加重。病程中伴恶心，无明显呕吐，无腹泻，无黑便及血便，无尿频尿急尿痛。自行服用止痛药后缓解不明显，遂至急诊就诊。急诊查血常规提示白细胞及中性粒细胞比例升高，腹部超声提示右下腹管状低回声结构，考虑阑尾炎可能，收入普通外科。
既往史：既往体健，否认高血压、糖尿病、冠心病、肝炎、结核等病史；否认腹部手术史；否认药物及食物过敏史。个人史无特殊，吸烟偶有，饮酒少量。家族史无特殊。
体格检查：T 37.8℃，P 96次/分，R 20次/分，BP 126/78mmHg。神志清楚，急性痛苦面容，步入病房时右下腹保护性姿势明显。腹部平坦，未见胃肠型及蠕动波，右下腹麦氏点压痛阳性，伴反跳痛及轻度肌紧张，肠鸣音稍弱。腰大肌试验可疑阳性，闭孔内肌试验阴性。实验室检查提示CRP轻度升高，肝肾功能及凝血功能未见明显异常。
入院诊断：急性阑尾炎。
诊疗计划：完善术前评估，禁食水，补液、抗感染、止痛对症治疗，告知患者及家属急性阑尾炎进展为化脓、穿孔及腹膜炎风险，拟急诊手术治疗。
手术情况：2026年2月6日行腹腔镜阑尾切除术，术中见阑尾充血水肿，周围少量渗出，无明显穿孔，完整切除阑尾并送病理检查，手术顺利。`,
  },
  {
    name: '社区获得性肺炎',
    admissionId: 'WW-003',
    medical_text: `入院记录

患者王五，女，65岁，因“咳嗽咳痰伴发热3天”入院。
主诉：咳嗽、咳黄痰伴发热3天。
现病史：患者3天前受凉后出现阵发性咳嗽，初为少量白痰，后转为黄色黏痰，痰量中等，不易咳出，伴畏寒、发热，体温最高39.2℃，自行口服退热药后可短暂下降。近1天出现活动后气促、乏力、食欲下降，夜间咳嗽明显影响睡眠，无胸痛咯血，无意识障碍，无明显腹痛腹泻。社区门诊予口服抗感染药物后症状改善不明显，遂来院就诊。急诊测血氧饱和度94%，查血常规提示白细胞升高，中性粒细胞比例增高，C反应蛋白升高。
既往史：有慢性支气管炎病史多年，冬春季易反复咳嗽；否认明确慢阻肺诊断史。既往有高血压病史8年，规律服药控制尚可；否认糖尿病、冠心病及肿瘤病史。否认药物及食物过敏史。无长期卧床史，无近期外地旅行史。
体格检查：T 38.6℃，P 102次/分，R 24次/分，BP 138/82mmHg。神志清楚，精神差，口唇无明显发绀。双肺呼吸音粗，双下肺可闻及湿啰音，右下肺较明显；心律齐，各瓣膜听诊区未闻及明显杂音；腹软，无压痛。胸部CT：双下肺感染性病变，右下肺实变影伴少量渗出，未见明显胸腔积液。
入院诊断：社区获得性肺炎。
诊疗计划：入院后予吸氧、补液、退热、监测血氧饱和度，完善痰培养、血培养、降钙素原、肝肾功能及电解质检查；结合患者年龄、发热、影像学改变及炎症指标，给予头孢曲松抗感染、氨溴索化痰、雾化吸入及对症支持治疗。治疗经过：经处理后体温逐步下降，咳痰较前减少，气促缓解，症状好转。`,
  },
]

const selectedCaseIndex = ref(0)
const medicalText = ref(testCases[0].medical_text)
const extracting = ref(false)
const grouping = ref(false)
const extractedData = ref<any>(null)
const drgResult = ref<any>(null)
const admissionId = ref<string | null>(testCases[0].admissionId)
const groupingType = ref<'DIP' | 'DRG'>('DIP')
const codeMappings = ref<Record<string, string>>({})
const preGroupingHistory = ref<PreGroupingSimulation[]>([])
const groupingCorrections = ref<GroupingCorrectionResult | null>(null)
const correctionsLoading = ref(false)

function isGroupingSuccess(status?: string): boolean {
  if (!status) return false
  return status.includes('成功') || status.toLowerCase().includes('success')
}

const hasExtractedData = computed(() => !!extractedData.value)
const currentCase = computed(() => testCases[selectedCaseIndex.value] || testCases[0])
const textLength = computed(() => (medicalText.value || '').replace(/\s+/g, '').length)
const latestPreGroupingSimulation = computed(() => preGroupingHistory.value[0] || null)
const preGroupingChangedFields = computed(
  () => latestPreGroupingSimulation.value?.change_tracking?.changed_fields || [],
)

const currentStageLabel = computed(() => {
  if (grouping.value) return '分组中'
  if (drgResult.value) return '预判完成'
  if (extracting.value) return '抽取中'
  if (hasExtractedData.value) return '待分组'
  return '待抽取'
})

const mainDiagnosis = computed(() => {
  const diags = extractedData.value?.diagnoses
  if (!diags) return null
  const code = diags.discharge_main_icd || diags.admission_main_icd || ''
  const text = diags.discharge_main_diagnosis_text || diags.admission_main_diagnosis_text || ''
  return code || text ? { code, text, mappedCode: codeMappings.value[code] || '' } : null
})

const secondaryDiagnoses = computed(() => {
  const diags = extractedData.value?.diagnoses
  if (!diags) return []
  const codes = diags.discharge_other_icds || diags.admission_other_icds || []
  const texts = diags.discharge_other_diagnoses_texts || diags.admission_other_diagnoses_texts || []
  return texts
    .map((text: string, idx: number) => ({
      code: codes[idx] || '',
      text,
      mappedCode: codeMappings.value[codes[idx]] || '',
    }))
    .slice(0, 5)
})

const diagnosisCount = computed(
  () => (mainDiagnosis.value ? 1 : 0) + secondaryDiagnoses.value.length,
)

function firstNonEmptyString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => (typeof item === 'string' ? item.trim() : '')).filter(Boolean)
}

function extractProcedureTextsFromMedicalText(text: string): string[] {
  if (!text) return []
  const matches = new Set<string>()
  const patterns = [
    /(?:行|施行)([^，。；\n]{2,40}?术)/g,
    /手术(?:情况|经过)?[:：]\s*([^，。；\n]{2,40}?术)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null = pattern.exec(text)
    while (match) {
      const candidate = (match[1] || '').trim()
      if (candidate && candidate.length <= 40) matches.add(candidate)
      match = pattern.exec(text)
    }
  }
  return Array.from(matches)
}

function inferProcedureCodeFromText(text: string): string {
  const normalized = (text || '').trim()
  if (!normalized) return ''

  // 先走关键词直连，覆盖本项目常见术式
  const keywordRules: Array<{ keywords: string[]; code: string }> = [
    { keywords: ['腹腔镜', '阑尾切除'], code: '47.0100' },
    { keywords: ['阑尾切除'], code: '47.0901' },
    { keywords: ['支架植入'], code: '36.0700' },
    { keywords: ['冠状动脉造影'], code: '88.5500' },
    { keywords: ['经皮冠状动脉介入'], code: '36.0700' },
  ]
  for (const rule of keywordRules) {
    if (rule.keywords.every((kw) => normalized.includes(kw))) return rule.code
  }

  // 再尝试 mock ICD-9 检索
  const candidates = searchICD9Procedures(normalized)
  if (candidates.length > 0) return candidates[0].code

  // 使用手术名称中的关键子串做降级检索
  const compact = normalized.replace(/术|手术|操作|及|与|行|腹腔镜/g, '').trim()
  if (compact.length >= 2) {
    const fallback = searchICD9Procedures(compact)
    if (fallback.length > 0) return fallback[0].code
  }
  return ''
}

function getNormalizedProcedures(
  data: any,
  sourceText: string,
): Array<{ code: string; text: string }> {
  const procs = data?.procedures || data?.surgeries || data?.operation || {}

  const mainCode = firstNonEmptyString(
    procs?.main_procedure_code,
    procs?.major_surgery_icd,
    procs?.major_surgery_code,
    procs?.main_surgery_code,
    procs?.main_operation_code,
  )
  const mainText = firstNonEmptyString(
    procs?.main_procedure_text,
    procs?.main_procedure_name,
    procs?.major_surgery_text,
    procs?.major_surgery_name,
    procs?.main_surgery_text,
    procs?.main_operation_text,
    procs?.main_operation_name,
    procs?.surgery_name,
  )

  const otherCodes = normalizeStringArray(
    procs?.other_procedure_codes ||
      procs?.other_surgery_icds ||
      procs?.other_surgery_codes ||
      procs?.other_operation_codes,
  )
  const otherTexts = normalizeStringArray(
    procs?.other_procedure_texts ||
      procs?.other_procedures_texts ||
      procs?.other_surgery_texts ||
      procs?.other_operation_texts ||
      procs?.other_procedure_names,
  )

  const result: Array<{ code: string; text: string }> = []
  if (mainText)
    result.push({ code: mainCode || inferProcedureCodeFromText(mainText), text: mainText })

  otherTexts.forEach((text, idx) => {
    result.push({ code: otherCodes[idx] || inferProcedureCodeFromText(text), text })
  })

  const otherProcObjects = Array.isArray(procs?.other_procedures) ? procs.other_procedures : []
  otherProcObjects.forEach((item: any) => {
    const text = firstNonEmptyString(
      item?.text,
      item?.name,
      item?.surgery_name,
      item?.operation_name,
    )
    const code = firstNonEmptyString(item?.code, item?.icd, item?.icd9, item?.surgery_code)
    if (text) result.push({ code: code || inferProcedureCodeFromText(text), text })
  })

  if (!result.length) {
    const fallbackTexts = extractProcedureTextsFromMedicalText(sourceText)
    fallbackTexts.forEach((text) => result.push({ code: inferProcedureCodeFromText(text), text }))
  }

  // 去重，避免字段重复映射导致重复展示
  const dedup = new Map<string, { code: string; text: string }>()
  result.forEach((item) => {
    const key = `${item.code}::${item.text}`
    if (!dedup.has(key)) dedup.set(key, item)
  })
  return Array.from(dedup.values()).slice(0, 5)
}

const procedures = computed(() => getNormalizedProcedures(extractedData.value, medicalText.value))

const profitClass = computed(() => {
  const profit = Number(drgResult.value?.profit)
  if (!Number.isFinite(profit)) return ''
  return profit >= 0 ? 'profit-positive' : 'profit-negative'
})

type MedicalTextSegment =
  | { type: 'text'; text: string }
  | { type: 'diag'; text: string }
  | { type: 'proc'; text: string }
  | { type: 'br' }

function appendTextWithBreaks(target: MedicalTextSegment[], text: string) {
  if (!text) return
  const lines = text.split('\n')
  lines.forEach((line, index) => {
    if (line) target.push({ type: 'text', text: line })
    if (index < lines.length - 1) target.push({ type: 'br' })
  })
}

const highlightedMedicalTextSegments = computed<MedicalTextSegment[]>(() => {
  const source = medicalText.value
  if (!source) return []

  const diagTerms: string[] = []
  if (mainDiagnosis.value?.text) diagTerms.push(mainDiagnosis.value.text)
  secondaryDiagnoses.value.forEach((item: { text?: string }) => {
    if (item.text) diagTerms.push(item.text)
  })

  const procTerms: string[] = []
  procedures.value.forEach((item: { text?: string }) => {
    if (item.text) procTerms.push(item.text)
  })

  const allTerms = [
    ...diagTerms.map((text) => ({ text: String(text).trim(), type: 'diag' as const })),
    ...procTerms.map((text) => ({ text: String(text).trim(), type: 'proc' as const })),
  ]
    .filter((item) => item.text.length > 0)
    .sort((a, b) => b.text.length - a.text.length)

  if (!allTerms.length) {
    const plain: MedicalTextSegment[] = []
    appendTextWithBreaks(plain, source)
    return plain
  }

  const matches: Array<{ start: number; end: number; type: 'diag' | 'proc' }> = []
  for (const term of allTerms) {
    let searchFrom = 0
    while (searchFrom < source.length) {
      const idx = source.indexOf(term.text, searchFrom)
      if (idx < 0) break
      const end = idx + term.text.length
      if (!matches.some((m) => idx < m.end && end > m.start)) {
        matches.push({ start: idx, end, type: term.type })
      }
      searchFrom = end
    }
  }
  matches.sort((a, b) => a.start - b.start)

  const segments: MedicalTextSegment[] = []
  let cursor = 0
  for (const match of matches) {
    if (match.start > cursor) {
      appendTextWithBreaks(segments, source.slice(cursor, match.start))
    }
    segments.push({ type: match.type, text: source.slice(match.start, match.end) })
    cursor = match.end
  }
  if (cursor < source.length) {
    appendTextWithBreaks(segments, source.slice(cursor))
  }
  return segments
})

function splitTraceCodeSegments(msg: string): Array<{ text: string; isCode: boolean }> {
  const source = String(msg || '')
  if (!source) return []
  const codeRegex = /([A-Z]\d{2}\.\d[\w.]*|\d{2}\.\d[\w.]*)/g
  const segments: Array<{ text: string; isCode: boolean }> = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = codeRegex.exec(source)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ text: source.slice(lastIndex, match.index), isCode: false })
    }
    segments.push({ text: match[0], isCode: true })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < source.length) {
    segments.push({ text: source.slice(lastIndex), isCode: false })
  }
  return segments
}

function preGroupingFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    pdx_code: '主诊断',
    adx_count: '其他诊断',
    procedure_count: '手术操作',
    patient_age: '年龄',
    patient_gender: '性别',
    los: '住院日',
    total_fee: '费用',
    medical_text: '病历文本',
  }
  return labels[field] || field
}

function formatSimulationTime(value: string): string {
  if (!value) return ''
  return value.replace('T', ' ').replace('Z', '').slice(0, 16)
}

async function loadPreGroupingHistory(visitId = currentCase.value.admissionId) {
  if (!visitId) {
    preGroupingHistory.value = []
    return
  }
  try {
    preGroupingHistory.value = await getPreGroupingHistory(visitId)
  } catch (error) {
    console.warn('加载预入组历史失败:', error)
    preGroupingHistory.value = []
  }
}

const handleCaseChange = (idx: number) => {
  selectedCaseIndex.value = idx
  medicalText.value = testCases[idx].medical_text
  extractedData.value = null
  drgResult.value = null
  groupingCorrections.value = null
  admissionId.value = testCases[idx].admissionId
  void loadPreGroupingHistory(testCases[idx].admissionId)
}

const handleMedicalTextEdited = () => {
  if (!extractedData.value && !drgResult.value && !groupingCorrections.value) return
  extractedData.value = null
  drgResult.value = null
  groupingCorrections.value = null
  preGroupingHistory.value = []
}

async function createBackendPreGroupingSimulation() {
  try {
    const simulation = await triggerAdmissionPreGrouping({
      visit_id: currentCase.value.admissionId,
      document_id: `${currentCase.value.admissionId}-admission-note`,
      medical_text: medicalText.value,
    })
    preGroupingHistory.value = [simulation, ...preGroupingHistory.value]
  } catch (error) {
    console.warn('创建后端预入组模拟历史失败:', error)
  }
}

function buildGroupingCorrectionInput(result: Record<string, unknown>) {
  const diagnoses = extractedData.value?.diagnoses || {}
  const proceduresData = extractedData.value?.procedures || extractedData.value?.surgeries || {}
  const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
  const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
  const mainProcCode = proceduresData.main_procedure_code || ''
  const otherProcCodes = proceduresData.other_procedure_codes || []
  const fallbackProcCodes = procedures.value.map((item) => item.code).filter(Boolean)
  const procCodes = Array.from(
    new Set([mainProcCode, ...otherProcCodes, ...fallbackProcCodes].filter(Boolean)),
  )
  return {
    pdx_code: primaryDiagCode,
    proc_codes: procCodes,
    grouping_result: result,
    diagnosis_candidates: [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean),
    procedure_candidates: procCodes,
  }
}

async function refreshGroupingCorrections(result: Record<string, unknown>) {
  correctionsLoading.value = true
  groupingCorrections.value = null
  try {
    groupingCorrections.value = await suggestGroupingCorrections(
      buildGroupingCorrectionInput(result),
    )
  } catch (error) {
    console.warn('生成预入组修正建议失败:', error)
  } finally {
    correctionsLoading.value = false
  }
}

const handleExtract = async () => {
  if (!medicalText.value.trim()) {
    message.warning('请先输入病历文本')
    return
  }

  extracting.value = true
  try {
    const token = getAccessToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch('/api/v1/case-front-page/extract-pre-group', {
      method: 'POST',
      headers,
      body: JSON.stringify({ medical_text: medicalText.value }),
    })
    const data = await response.json()

    if (response.ok && data.success && data.data) {
      extractedData.value = data.data
      admissionId.value = data.data.admission_id
      await createBackendPreGroupingSimulation()
      await loadPreGroupingHistory(currentCase.value.admissionId)
      message.success('AI 智能抽取完成')
      extracting.value = false
      await handleDIPGrouping()
    } else {
      const errorText = data.error || data.detail || '抽取失败'
      if (response.status === 401) {
        message.error('登录状态已失效，请重新登录后再执行抽取')
      } else {
        message.error(errorText)
      }
    }
  } catch (error) {
    console.error('Extract error:', error)
    message.error('AI 抽取服务暂不可用')
  } finally {
    extracting.value = false
  }
}

const handleDIPGrouping = async () => {
  if (!extractedData.value || extracting.value) {
    message.warning('请先完成 AI 抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DIP'
  groupingCorrections.value = null

  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const proceduresData = extractedData.value.procedures || extractedData.value.surgeries || {}
    const costs = extractedData.value.costs || {}

    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes =
      diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = proceduresData.main_procedure_code || ''
    const otherProcCodes = proceduresData.other_procedure_codes || []

    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const fallbackProcCodes = procedures.value.map((item) => item.code).filter(Boolean)
    const ssList = Array.from(
      new Set([mainProcCode, ...otherProcCodes, ...fallbackProcCodes].filter(Boolean)),
    )

    const dipResult = localDipGrouping({ zdList, ssList })

    if (isGroupingSuccess(dipResult.status)) {
      drgResult.value = {
        code: dipResult.dipCode || '未入组',
        name: dipResult.dipName || '未知病种',
        groupingType: 'DIP',
        weight: '--',
        payment: '--',
        actual_cost: costs.total_cost || 0,
        profit: '--',
        matchType: dipResult.matchType || '',
        score: dipResult.score,
        diseaseAttribute: dipResult.diseaseAttribute,
        primaryCareFlag: dipResult.primaryCareFlag,
        messages: dipResult.messages,
      }
      message.success(`泸州 DIP 入组成功: ${dipResult.dipCode}`)
      await refreshGroupingCorrections(drgResult.value)
    } else {
      drgResult.value = {
        code: '未入组',
        name: '无法匹配病种',
        groupingType: 'DIP',
        weight: '--',
        payment: '--',
        actual_cost: costs.total_cost || 0,
        profit: '--',
        messages: dipResult.messages,
      }
      message.warning('DIP 未能入组')
      await refreshGroupingCorrections(drgResult.value)
    }
  } catch (error) {
    console.error('DIP grouping error:', error)
    message.error('DIP 本地分组引擎执行失败')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}

const handleDRGGrouping = async () => {
  if (!extractedData.value || extracting.value) {
    message.warning('请先完成 AI 抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DRG'
  groupingCorrections.value = null

  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const proceduresData = extractedData.value.procedures || extractedData.value.surgeries || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}

    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes =
      diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = proceduresData.main_procedure_code || ''
    const otherProcCodes = proceduresData.other_procedure_codes || []

    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const fallbackProcCodes = procedures.value.map((item) => item.code).filter(Boolean)
    const ssList = Array.from(
      new Set([mainProcCode, ...otherProcCodes, ...fallbackProcCodes].filter(Boolean)),
    )

    const drgGroupResult = await localDrgGrouping({
      gender: basicInfo.gender === '2' || basicInfo.gender_text === '女' ? '2' : '1',
      age: basicInfo.age_years || 50,
      zdList,
      ssList,
      days: 7,
    })

    const actualCost = costs.total_cost || 0

    if (isGroupingSuccess(drgGroupResult.status) && drgGroupResult.drg) {
      const rw = drgGroupResult.rw || 0
      const baselinePayment = Math.round(rw * 8000 * 100) / 100
      drgResult.value = {
        code: drgGroupResult.drg,
        name:
          drgGroupResult.drgName ||
          `MDC ${drgGroupResult.mdc || '--'} / ADRG ${drgGroupResult.adrg || '--'}`,
        groupingType: 'DRG',
        weight: rw,
        payment: baselinePayment,
        actual_cost: actualCost,
        profit: Math.round((baselinePayment - actualCost) * 100) / 100,
        isLowRisk: drgGroupResult.isLowRisk,
        weightSource: drgGroupResult.weightSource,
        messages: drgGroupResult.messages,
      }
      message.success(`四川 DRG 入组成功: ${drgGroupResult.drg} (RW=${rw})`)
      await refreshGroupingCorrections(drgResult.value)
    } else {
      drgResult.value = {
        code: '未入组',
        name: drgGroupResult.adrg ? `ADRG: ${drgGroupResult.adrg}` : '无法入组',
        groupingType: 'DRG',
        weight: 0,
        payment: 0,
        actual_cost: actualCost,
        profit: -actualCost,
        messages: drgGroupResult.messages,
      }
      message.warning('DRG 未能入组')
      await refreshGroupingCorrections(drgResult.value)
    }
  } catch (error) {
    console.error('DRG grouping error:', error)
    message.error('DRG 本地分组引擎执行失败')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}

onMounted(() => {
  void loadPreGroupingHistory()
})
</script>

<style scoped src="../../styles/drg-pre-analysis.css"></style>
<style scoped src="./drg-dip-workbench.css"></style>
