<template>
  <div class="hm-frontpage-preview">
    <div class="toolbar">
      <a-space>
        <a-button :disabled="!srcdoc" @click="printIframe">打印</a-button>
        <a-typography-text type="secondary" class="hint">
          基于 HM 模板回填（仅展示/打印，一期不含编辑交互）
        </a-typography-text>
      </a-space>
    </div>
    
    <div class="frame-wrap">
      <iframe ref="iframeRef" class="preview-frame" :srcdoc="srcdoc" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'

import templateBodyHtml from '@/assets/templates/hm-frontpage/inpatient_record.html?raw'
import contentsCss from '@/assets/templates/hm-frontpage/contents.css?raw'
import printCss from '@/assets/templates/hm-frontpage/print.css?raw'

import { applyDeValuesToHmTemplateBody, buildHmTemplateSrcdoc } from '@/utils/hm-frontpage/templateRefill'
import { frontPageDraftToDeMap } from '@/utils/hm-frontpage/frontPageDraftToDeMap'

const props = defineProps<{
  draft: any | null
}>()

const iframeRef = ref<HTMLIFrameElement | null>(null)

const srcdoc = computed(() => {
  // Always render the template, use empty object if no draft data
  const draftData = props.draft || {}
  const valuesByDe = frontPageDraftToDeMap(draftData)
  const filledBodyHtml = applyDeValuesToHmTemplateBody(templateBodyHtml, valuesByDe)
  return buildHmTemplateSrcdoc({ filledBodyHtml, contentsCss, printCss })
})

function printIframe() {
  const iframeWindow = iframeRef.value?.contentWindow
  if (!iframeWindow) {
    message.error('预览尚未加载完成')
    return
  }
  iframeWindow.focus()
  iframeWindow.print()
}
</script>

<style scoped>
.hm-frontpage-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.hint {
  font-size: 12px;
}

.frame-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow-y: auto;
  overflow-x: hidden;
  background: #fff;
  max-height: calc(100vh - 200px);
}

.preview-frame {
  width: 100%;
  min-height: 2500px;
  height: auto;
  border: 0;
  background: #fff;
}
</style>

