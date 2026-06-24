/**
 * 缺陷高亮 Composable
 *
 * 核心功能:
 * - 在文书文本中注入高亮标记
 * - 缺陷→正文锚点定位
 * - 高亮区域点击→右侧面板联动
 */

import { ref, computed, nextTick } from 'vue'

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

/** 严重级别样式映射 */
const SEVERITY_STYLES: Record<string, { bg: string; border: string; text: string }> = {
    critical: { bg: '#fef2f2', border: '#ef4444', text: '#dc2626' },
    error: { bg: '#fff7ed', border: '#f97316', text: '#ea580c' },
    warning: { bg: '#fefce8', border: '#eab308', text: '#ca8a04' },
    info: { bg: '#eff6ff', border: '#3b82f6', text: '#2563eb' },
}

export function useDefectHighlight() {
    const activeDefectId = ref<string | null>(null)
    const clickCallback = ref<((defectId: string) => void) | null>(null)

    /**
     * 将纯文本内容注入缺陷高亮标记，返回 HTML 字符串
     */
    function highlightDefects(content: string, annotations: DefectAnnotation[]): string {
        if (!content) return ''

        // ① 段落标题列表（块级显示，不内联）
        const SECTION_TITLES = [
            '主诉', '现病史', '既往史', '个人史', '家族史', '体格检查', '辅助检查',
            '首次病程', '病情摘要', '诊断', '入院诊断', '出院诊断', '门诊诊断',
            '门（急）诊诊断', '处理意见', '治疗经过', '过敏史', '婚育史',
            '手术史', '病史小结', '初步诊断', '修正诊断', '补充诊断'
        ]

        // 段落标题注入（块级 span，顶部有 margin-top）
        const injectSectionTitles = (text: string): string => {
            const titleRegex = new RegExp(
                `(^|\\n)(${SECTION_TITLES.join('|')})[：:]`,
                'g'
            )
            return text.replace(titleRegex, (match, prefix, title) => {
                const colon = match.endsWith('：') ? '：' : ':'
                const marginTop = prefix === '' ? '' : ''
                return `${prefix}<span class="emr-section-title">${title}${colon}</span>`
            })
        }

        if (!annotations?.length) {
            const escaped = escapeHtml(content)
            return injectSectionTitles(escaped)
        }

        // ② 缺陷高亮：极浅底色 + 虚线下划线 + hover tooltip 卡片
        const SEVERITY_LABEL: Record<string, string> = {
            critical: 'AI 严重缺陷',
            error: 'AI 错误',
            warning: 'AI 警告',
            info: 'AI 提示',
        }

        const validAnnotations = annotations
            .filter(a => a.start_offset >= 0 && a.end_offset > a.start_offset)
            .sort((a, b) => b.start_offset - a.start_offset)

        let result = content

        for (const annotation of validAnnotations) {
            const { start_offset, end_offset, defect_id, severity, description, suggestion } = annotation
            const before = result.slice(0, start_offset)
            const highlighted = result.slice(start_offset, end_offset)
            const after = result.slice(end_offset)
            const label = SEVERITY_LABEL[severity] || 'AI 提示'

            const tooltipContent = suggestion
                ? `<div class="emr-defect-tip__body">${escapeHtml(description)}</div><div class="emr-defect-tip__suggest">💡 ${escapeHtml(suggestion)}</div>`
                : `<div class="emr-defect-tip__body">${escapeHtml(description)}</div>`

            const defectSpan = `<span class="emr-defect emr-defect--${severity}" data-defect-id="${defect_id}" data-severity="${severity}">${escapeHtml(highlighted)}<span class="emr-defect-tip"><span class="emr-defect-tip__header emr-defect-tip__header--${severity}">${label}</span>${tooltipContent}</span></span>`

            result = before + defectSpan + after
        }

        // ③ 注入段落标题
        result = injectSectionTitles(escapeHtml(result).replace(/&amp;lt;/g, '<').replace(/&amp;gt;/g, '>'))

        return result
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
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}
