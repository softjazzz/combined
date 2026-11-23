/**
 * 缺陷高亮 Composable
 *
 * 核心功能:
 * - 在文书文本中注入高亮标记
 * - 缺陷→正文锚点定位
 * - 高亮区域点击→右侧面板联动
 */

import { ref, nextTick } from 'vue'

/** 缺陷标注 */
export interface DefectAnnotation {
    defect_id: string
    start_offset: number
    end_offset: number
    keyword: string
    description: string
    evidence?: string
    severity: 'critical' | 'error' | 'warning' | 'info'
    rule_name: string
    category: string
    suggestion?: string
}

export type HighlightSeverity = 'critical' | 'error' | 'warning' | 'info'

export type EmrHighlightSegment =
    | { type: 'text'; text: string }
    | { type: 'section_title'; text: string }
    | {
        type: 'defect'
        text: string
        defectId: string
        severity: HighlightSeverity
        severityLabel: string
        description: string
        suggestion: string
    }

const SECTION_TITLES = [
    '主诉', '现病史', '既往史', '个人史', '家族史', '体格检查', '辅助检查',
    '首次病程', '病情摘要', '诊断', '入院诊断', '出院诊断', '门诊诊断',
    '门（急）诊诊断', '处理意见', '治疗经过', '过敏史', '婚育史',
    '手术史', '病史小结', '初步诊断', '修正诊断', '补充诊断'
]

const SEVERITY_LABEL: Record<HighlightSeverity, string> = {
    critical: 'AI 严重缺陷',
    error: 'AI 错误',
    warning: 'AI 警告',
    info: 'AI 提示',
}

function normalizeSeverity(severity: unknown): HighlightSeverity {
    if (severity === 'critical' || severity === 'error' || severity === 'warning' || severity === 'info') {
        return severity
    }
    return 'info'
}

function splitPlainTextWithSectionTitles(text: string): EmrHighlightSegment[] {
    if (!text) return []
    const titleRegex = new RegExp(`(^|\\n)(${SECTION_TITLES.join('|')})([：:])`, 'g')
    const segments: EmrHighlightSegment[] = []
    let lastIndex = 0
    let match: RegExpExecArray | null

    while ((match = titleRegex.exec(text)) !== null) {
        const prefix = match[1] || ''
        const titleWithColon = `${match[2]}${match[3]}`
        const titleStart = match.index + prefix.length

        if (titleStart > lastIndex) {
            segments.push({ type: 'text', text: text.slice(lastIndex, titleStart) })
        }
        segments.push({ type: 'section_title', text: titleWithColon })
        lastIndex = titleStart + titleWithColon.length
    }

    if (lastIndex < text.length) {
        segments.push({ type: 'text', text: text.slice(lastIndex) })
    }
    return segments
}

/**
 * 将纯文本与缺陷标注拆分为结构化文本片段，供 Vue 文本插值安全渲染（避免 v-html XSS）
 */
export function buildHighlightedSegments(
    content: string,
    annotations: DefectAnnotation[] = [],
): EmrHighlightSegment[] {
    if (!content) return []
    if (!annotations?.length) {
        return splitPlainTextWithSectionTitles(content)
    }

    const sorted = annotations
        .map((ann) => ({
            ann,
            start: Math.max(0, Math.min(content.length, Math.floor(Number(ann.start_offset)))),
            end: Math.max(0, Math.min(content.length, Math.floor(Number(ann.end_offset)))),
        }))
        .filter((item) => Number.isFinite(item.start) && Number.isFinite(item.end) && item.end > item.start)
        .sort((a, b) => (a.start !== b.start ? a.start - b.start : b.end - a.end))

    const segments: EmrHighlightSegment[] = []
    let cursor = 0

    for (const { ann, start, end } of sorted) {
        if (start < cursor) continue
        if (start > cursor) {
            segments.push(...splitPlainTextWithSectionTitles(content.slice(cursor, start)))
        }
        const severity = normalizeSeverity(ann.severity)
        segments.push({
            type: 'defect',
            text: content.slice(start, end),
            defectId: String(ann.defect_id || ''),
            severity,
            severityLabel: SEVERITY_LABEL[severity],
            description: String(ann.description || ''),
            suggestion: String(ann.suggestion || ''),
        })
        cursor = end
    }

    if (cursor < content.length) {
        segments.push(...splitPlainTextWithSectionTitles(content.slice(cursor)))
    }
    return segments
}

export function useDefectHighlight() {
    const activeDefectId = ref<string | null>(null)
    const clickCallback = ref<((defectId: string) => void) | null>(null)

    /**
     * 将纯文本内容注入缺陷高亮标记，返回单次安全转义的 HTML 字符串（兼容旧调用方）
     */
    function highlightDefects(content: string, annotations: DefectAnnotation[]): string {
        return buildHighlightedSegments(content, annotations)
            .map((segment) => {
                if (segment.type === 'text') {
                    return escapeHtml(segment.text)
                }
                if (segment.type === 'section_title') {
                    return `<span class="emr-section-title">${escapeHtml(segment.text)}</span>`
                }
                const tooltipContent = segment.suggestion
                    ? `<div class="emr-defect-tip__body">${escapeHtml(segment.description)}</div><div class="emr-defect-tip__suggest">💡 ${escapeHtml(segment.suggestion)}</div>`
                    : `<div class="emr-defect-tip__body">${escapeHtml(segment.description)}</div>`
                return `<span class="emr-defect emr-defect--${segment.severity}" data-defect-id="${escapeAttr(segment.defectId)}" data-severity="${segment.severity}">${escapeHtml(segment.text)}<span class="emr-defect-tip"><span class="emr-defect-tip__header emr-defect-tip__header--${segment.severity}">${escapeHtml(segment.severityLabel)}</span>${tooltipContent}</span></span>`
            })
            .join('')
    }

    /**
     * 滚动到指定缺陷的锚点位置
     */
    function scrollToDefect(defectId: string, container?: HTMLElement) {
        activeDefectId.value = defectId

        nextTick(() => {
            const target = container || document
            const el = target.querySelector(`[data-defect-id="${defectId}"]`) as HTMLElement
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' })

                // 闪烁高亮效果
                el.style.outline = '3px solid #3b82f6'
                el.style.outlineOffset = '2px'
                setTimeout(() => {
                    el.style.outline = 'none'
                }, 2000)
            }
        })
    }

    /**
     * 注册高亮区域点击回调
     */
    function onDefectClick(callback: (defectId: string) => void) {
        clickCallback.value = callback
    }

    /**
     * 绑定容器的点击事件监听（在 onMounted 中调用）
     */
    function bindClickEvents(container: HTMLElement) {
        container.addEventListener('click', (e) => {
            const target = (e.target as HTMLElement).closest('[data-defect-id]') as HTMLElement
            if (target) {
                const defectId = target.dataset.defectId
                if (defectId) {
                    activeDefectId.value = defectId
                    clickCallback.value?.(defectId)
                }
            }
        })
    }

    return {
        activeDefectId,
        buildHighlightedSegments,
        highlightDefects,
        scrollToDefect,
        onDefectClick,
        bindClickEvents,
    }
}

// ============= 工具函数 =============

function escapeHtml(text: string): string {
    if (!text) return ''
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
}

function escapeAttr(text: string): string {
    if (!text) return ''
    return escapeHtml(text)
}
