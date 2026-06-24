$path = "src/views/workstation-v2/components/FrontpageSheet.vue"
$content = Get-Content -Raw -Path $path

$start = $content.IndexOf("<script setup>")
if ($start -lt 0) { throw "script tag start not found" }
$end = $content.IndexOf("</script>", $start)
if ($end -lt 0) { throw "script tag end not found" }
$end = $end + "</script>".Length

$newScript = @'
<script setup>
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
  postProcessing: { type: Boolean, default: false }
})

function b(field) {
  return props.data?.basic?.[field] || ''
}

function t(field) {
  const v = props.data?.basic?.[field]
  return !v || v === '/' || v === '-' ? '' : v
}

function c(field) {
  const val = props.data?.cost?.[field]
  if (!val || val === 'None') return ''
  const num = parseFloat(val)
  return Number.isNaN(num) ? val : num.toFixed(2)
}

function dateParts(val) {
  if (!val) return { year: '', month: '', day: '', hour: '' }
  const m = String(val).match(/(\d{4})-(\d{2})-(\d{2})\s*(\d{2})?/)
  if (m) return { year: m[1], month: m[2], day: m[3], hour: m[4] || '' }
  return { year: '', month: '', day: '', hour: '' }
}

function formatDateShort(val) {
  if (!val) return ''
  const m = String(val).match(/(\d{4})-(\d{2})-(\d{2})/)
  if (m) return `${m[1]}-${m[2]}-${m[3]}`
  return String(val)
}

const PAYMENT_MAP = {
  城镇职工基本医疗保险: '1',
  城镇职工: '1',
  城镇居民基本医疗保险: '2',
  城镇居民: '2',
  新型农村合作医疗: '3',
  新农合: '3',
  贫困救助: '4',
  商业医疗保险: '5',
  商业保险: '5',
  全公费: '6',
  全自费: '7',
  自费: '7',
  其他社会保险: '8',
  其他: '9'
}

const paymentCode = computed(() => {
  const raw = String(b('medical_payment_method') || '').trim()
  if (!raw) return ''
  if (/^\d$/.test(raw)) return raw
  return PAYMENT_MAP[raw] || raw.charAt(0)
})

function parseProvCity(val) {
  const text = String(val || '').trim()
  if (!text) return { prov: '', city: '' }
  const m = text.match(/^(.*?(?:省|自治区|特别行政区|市))(.*?(?:市|州|盟))?/)
  if (!m) return { prov: text, city: '' }
  return { prov: (m[1] || '').trim(), city: (m[2] || '').trim() }
}

function parseAddress(val) {
  const text = String(val || '').trim()
  if (!text) return { prov: '', city: '', county: '' }
  const m = text.match(/^(.*?(?:省|自治区|特别行政区|市))?(.*?(?:市|州|盟))?(.*?(?:区|县|旗))?/)
  return {
    prov: (m?.[1] || '').trim(),
    city: (m?.[2] || '').trim(),
    county: (m?.[3] || '').trim()
  }
}

const computedAge = computed(() => {
  const bd = b('birthday')
  if (!bd) return ''
  try {
    const birth = new Date(bd)
    const now = new Date()
    let age = now.getFullYear() - birth.getFullYear()
    if (
      now.getMonth() < birth.getMonth() ||
      (now.getMonth() === birth.getMonth() && now.getDate() < birth.getDate())
    ) {
      age -= 1
    }
    if (age >= 1) return String(age)
    const months = Math.max(0, Math.floor((now - birth) / (1000 * 60 * 60 * 24 * 30)))
    return `${months}月`
  } catch {
    return ''
  }
})

const diagnosisPairs = computed(() => {
  const diags = Array.isArray(props.data?.diagnoses) ? props.data.diagnoses : []
  const mainIdx = diags.findIndex(d => String(d?.diagnosis_type || '').includes('主要'))
  const mainDiag = mainIdx >= 0 ? [diags[mainIdx]] : []
  const otherDiag = diags.filter((_, idx) => idx !== mainIdx)
  const leftItems = [...mainDiag, ...otherDiag.slice(0, Math.ceil(otherDiag.length / 2))]
  const rightItems = otherDiag.slice(Math.ceil(otherDiag.length / 2))
  const rowCount = Math.max(leftItems.length, rightItems.length, 10)
  const pairs = []
  for (let i = 0; i < rowCount; i += 1) {
    pairs.push({ left: leftItems[i] || null, right: rightItems[i] || null })
  }
  return pairs
})

const paddedSurgeries = computed(() => {
  const s = Array.isArray(props.data?.surgeries) ? props.data.surgeries : []
  const rows = [...s]
  while (rows.length < 8) rows.push({ surgery_code: '', surgery_name: '', surgeon: '' })
  return rows
})

function formatIncision(s) {
  if (!s?.surgery_name && !s?.surgery_code) return ''
  if (!s?.surgial_incision_level && !s?.surgical_incisionheal_level) return '/'
  return `${s?.surgial_incision_level || ''} / ${s?.surgical_incisionheal_level || ''}`
}

function normalizeEvidenceKey(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^\u4e00-\u9fa5a-z0-9]/gi, '')
}

const diagnosisEvidenceList = computed(() => {
  const arr = props.data?.evidence?.diagnoses
  return Array.isArray(arr) ? arr : []
})

const diagnosisEvidenceMap = computed(() => {
  const m = new Map()
  diagnosisEvidenceList.value.forEach(item => {
    const key = normalizeEvidenceKey(item?.diagnosis_text)
    if (key && !m.has(key)) m.set(key, item)
  })
  return m
})

function findDiagnosisEvidence(name) {
  const key = normalizeEvidenceKey(name)
  if (!key) return null
  const direct = diagnosisEvidenceMap.value.get(key)
  if (direct) return direct
  return diagnosisEvidenceList.value.find(item => {
    const k = normalizeEvidenceKey(item?.diagnosis_text)
    return k && (k.includes(key) || key.includes(k))
  }) || null
}

const evidencePanel = reactive({
  visible: false,
  item: null
})

const showAllRawEvidence = ref(false)

const evidenceRawLines = computed(() => {
  const lines = evidencePanel.item?.raw_evidence_lines
  return Array.isArray(lines) ? lines : []
})

const hasMoreRawEvidence = computed(() => evidenceRawLines.value.length > 3)

const evidenceRawLinesToShow = computed(() => {
  if (showAllRawEvidence.value) return evidenceRawLines.value
  return evidenceRawLines.value.slice(0, 3)
})

function toggleRawEvidenceExpand() {
  showAllRawEvidence.value = !showAllRawEvidence.value
}

function openDiagnosisEvidence(name) {
  const item = findDiagnosisEvidence(name)
  if (!item) return
  evidencePanel.item = item
  evidencePanel.visible = true
  showAllRawEvidence.value = false
}

function closeDiagnosisEvidence() {
  evidencePanel.visible = false
  evidencePanel.item = null
  showAllRawEvidence.value = false
}

const diagnosisGenerationPending = computed(() => {
  if (!props.postProcessing) return false
  const list = Array.isArray(props.data?.diagnoses) ? props.data.diagnoses : []
  if (!list.length) return true
  const meaningful = list.filter(d => String(d?.diagnosis_name || '').trim().length > 0)
  if (!meaningful.length) return true
  const hasMissingCode = meaningful.some(d => String(d?.diagnosis_code || '').trim().length === 0)
  const hasEvidence = diagnosisEvidenceList.value.length > 0
  return hasMissingCode || !hasEvidence
})
</script>
'@

$newContent = $content.Substring(0, $start) + $newScript + $content.Substring($end)
Set-Content -Path $path -Value $newContent -Encoding UTF8
