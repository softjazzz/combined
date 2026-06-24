---
version: alpha
name: medqc-workstation-design
description: Use when designing, reviewing, or implementing UI for the MedQC medical quality-control workstation, including overview dashboards, medical-record pools, worklists, QC assistant/chatbot panels, ICD coding, DRG/DIP grouping, risk insight cards, filters, task queues, and dense medical admin pages. Enforces a clean, minimal, premium light medical back-office style consistent with workstation-v4.
colors:
  primary: "#2563eb"
  primary-soft: "#eaf2ff"
  canvas: "#f5f9fc"
  surface: "#ffffff"
  surface-muted: "#f8fbff"
  border: "#e2e8f0"
  text: "#0f172a"
  text-muted: "#64748b"
  text-subtle: "#94a3b8"
  success: "#10b981"
  warning: "#f59e0b"
  danger: "#ef4444"
  cyan: "#06b6d4"
  sidebar: "#0f1b2d"
typography:
  fontFamily: "Inter, PingFang SC, Microsoft YaHei, system-ui, sans-serif"
  page-title: "28px / 36px / 800"
  section-title: "20px / 28px / 800"
  body: "14px / 22px / 500"
  label: "13px / 18px / 700"
rounded:
  control: 8px
  panel: 12px
  large-panel: 18px
---

# MedQC Workstation Design

Design MedQC as a quiet, high-trust medical operations system. It should feel clear, restrained, and professional, not like a marketing dashboard or a generic chatbot.

Use this skill for `workstation-v4` and adjacent medical back-office pages: 质控首页概览, 病历池, 高优先级任务, 病案智能助手, 编码查询, DRG/DIP 入组, 风险洞察, 质控结果, 病历列表, and dense work queues.

## Visual Direction

- Use a light medical admin style: pale blue-gray canvas, white surfaces, weak borders, soft depth.
- Keep the dark navy sidebar as the main brand anchor. Do not add large dark page sections.
- Use blue only for primary actions, selected states, active metrics, and links.
- Use red/orange only for real risk, overdue, failed, or warning states.
- Prefer whitespace, alignment, typography, and row separators before adding cards, borders, or shadows.
- Avoid decorative blobs, bokeh, gradient orbs, large hero art, cartoon robots, and Apple/macOS visual language.
- Do not put cards inside cards. Repeated objects can be cards; whole page sections should usually be surfaces or bands.

## Layout System

Use this hierarchy for workstation pages:

1. Header: breadcrumb, page title, short operational subtitle, key actions.
2. Filter/Summary: compact search/filter strip and KPI strip.
3. Priority Area: highest-value queue or risk group.
4. Details/List: dense scannable table or list for real work.
5. Insight Sidebar: rankings, risk reasons, current changes, or guidance.

Avoid huge blank chart panels. If no meaningful trend data exists, show a useful list, queue, summary, or empty state with next action.

## Core Components

### Page Header

- Title should be literal and operational: `质控首页概览`, `病历池`, `病案智能助手`.
- Subtitle explains what the page helps users do, not marketing value.
- Keep action buttons compact and aligned right.
- Do not use oversized hero sections for back-office tools.

### Filter Strip

- Use one compact row where possible: search, date, department, status/process, query/reset.
- Search placeholder should match the workflow, for example `搜索患者、住院号、科室`.
- Show active filter summary as a small chip only when useful.
- Avoid spreading filters across multiple tall cards.

### KPI Cards

- KPI cards should be compact and comparable.
- Recommended content: label, value, short helper text or delta, optional small icon circle.
- Avoid oversized numbers inside compact dashboard surfaces.
- Four metrics per row is appropriate on desktop; collapse responsibly on smaller widths.

### Priority Queue

- Prefer one grouped surface with lightweight repeated cards or rows.
- Each item should expose: patient/visit id, department, status/risk tag, time pressure, primary action.
- Keep cards small enough to scan. Do not make every patient card a large floating tile.
- One active or most urgent item may use a stronger blue accent.

### Worklist / Table

Use list-table hybrids for high-volume pages like 病历池.

Recommended columns: 患者信息, 科室, 状态, 风险标签, 入院/出院, 更新时间, 操作.

Keep row height readable, use subtle separators, and avoid narrow Chinese columns that wrap character-by-character.

### Insight Panel

Use the right side for compact decision support: 科室风险排行, 优先池分组, 风险原因 TopN, 今日变化, AI 洞察, 下一步建议.

Do not make each insight row a separate heavy card. Use grouped rows with numbers aligned right.

### Assistant / Chatbot Panel

The assistant is a medical work panel, not a normal chatbot.

- Header subtitle: `单病历只读分析，支持质控、编码、入组模拟`.
- Show capability chips: `质控`, `编码`, `DRG-DIP`.
- Preserve safety language: 只读模式, 已脱敏, 不写正式结果表.
- Empty state should show three capability groups: 质控, 编码, 入组.
- Results should be structured cards by type: QC result, ICD search, coding suggestion, DRG grouping, DIP grouping, clarification, confirmation, unsupported.
- Do not show raw model output, embedding, vector paths, prompt, documents, medical_text, bundle, or internal data.

## Page Patterns

### 质控首页概览

Use a dashboard pattern: summary/filter header, KPI strip, risk insight panel, high-priority task table. The first screen should answer: What needs attention now?

### 病历池

Use an operations queue pattern: compact summary and filters, priority processing lane, full medical-record list, insight sidebar. Avoid scattered patient cards as the only browsing method for hundreds of records.

### 病案智能助手

Use a right drawer work panel: capability status, current record context, grouped quick actions, structured result cards, fixed bottom composer. The user should feel they are operating a safe analysis tool, not chatting with a generic bot.

## Interaction Rules

- Primary actions use filled blue buttons: `立即处理`, `执行分析`, `查询`.
- Secondary actions use outline or text buttons: `重置`, `刷新`, `标记稍后`.
- Chips and segmented controls should be small, calm, and data-rich.
- Loading and empty states should tell users what is happening and what they can do next.
- If a backend capability is unavailable, say `该能力待接入`; do not fake a successful result.

## Implementation Guardrails

- Reuse existing `workstation-v4` tokens, containers, Ant Design Vue patterns, and local components where practical.
- Do not invent a separate visual language for one page.
- Do not modify backend contracts for pure presentation unless compatibility and fallback are explicit.
- Do not add `.vue.ts` mirror files.
- Keep text UTF-8 and avoid mojibake.
- Before finishing implementation work, run at least `npm run check:encoding`, `npm run lint`, and `npm run type-check`.
- If changing shared behavior or task/result flows, also run `npm run test:unit`.
