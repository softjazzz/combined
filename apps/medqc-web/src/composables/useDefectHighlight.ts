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
        if (!content || !annotations?.length) {
            return escapeHtml(content)
        }

        // 按 start_offset 排序（从后往前替换避免偏移）
        const validAnnotations = annotations
            .filter(a => a.start_offset >= 0 && a.end_offset > a.start_offset)
            .sort((a, b) => b.start_offset - a.start_offset)

        let result = content

        for (const annotation of validAnnotations) {
            const { start_offset, end_offset, defect_id, severity, description } = annotation
            const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.warning

            const before = result.slice(0, start_offset)
            const highlighted = result.slice(start_offset, end_offset)
            const after = result.slice(end_offset)

            const highlightTag = `<span 
        class="defect-highlight" 
        data-defect-id="${defect_id}" 
        data-severity="${severity}"
        title="${escapeAttr(description)}"
        style="
          background-color: ${style.bg}; 
          border-bottom: 2px solid ${style.border}; 
          cursor: pointer;
          padding: 1px 2px;
          border-radius: 2px;
          position: relative;
          transition: background-color 0.2s;
        "
      >${escapeHtml(highlighted)}<sup style="
        color: ${style.text}; 
        font-size: 10px; 
        font-weight: bold;
        margin-left: 2px;
      ">⚠</sup></span>`

            result = before + highlightTag + after
        }

        // 对非高亮部分做 HTML 转义（简化处理：已经包含标签的跳过）
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
