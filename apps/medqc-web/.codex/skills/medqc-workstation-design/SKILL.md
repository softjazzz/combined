---
version: alpha
name: medqc-workstation-design
description: Use when designing, reviewing, or implementing UI for the MedQC medical quality-control workstation, including overview dashboards, medical-record pools, worklists, QC assistant/chatbot panels, ICD coding, DRG/DIP grouping, risk insight cards, filters, task queues, and dense medical admin pages. Enforces a clean, minimal, premium light medical back-office style consistent with workstation-v4.
colors:
  primary: '#0066cc'
  primary-dark-mode: '#2997FF'
  primary-soft: '#eaf2ff'
  canvas: '#f5f5f7'
  surface: '#ffffff'
  surface-glass: 'rgba(255,255,255,0.86)'
  surface-muted: '#e8e8ed'
  border: 'rgba(0,0,0,0.08)'
  text: '#1d1d1f'
  text-muted: 'rgba(29,29,31,0.60)'
  text-subtle: 'rgba(29,29,31,0.38)'
  success: '#10b981'
  warning: '#f59e0b'
  danger: '#ef4444'
  cyan: '#06b6d4'
  sidebar: 'rgba(255,255,255,0.86)'
typography:
  fontFamily: 'Source Han Sans SC, San Francisco, SF Pro Text, SF Pro Display, Inter, PingFang SC, Microsoft YaHei UI, Microsoft YaHei, system-ui, sans-serif'
  page-title: '28px / 31px / 700'
  section-title: '17px / 22px / 600'
  body: '14px / 22px / 500'
  label: '11-13px / 18px / 500-600'
rounded:
  control: 8px
  panel: 16px
  large-panel: 20px
effects:
  glass: 'background: rgba(255,255,255,.82-.90); backdrop-filter: blur(18px-20px); border: 1px solid rgba(0,0,0,.08)'
  hover: 'transform: translateY(-2px); box-shadow: 0 2px 12px rgba(0,0,0,.10), 0 6px 22px rgba(0,0,0,.075)'
  transition: '250-300ms cubic-bezier(.25,.1,.25,1)'
---

# MedQC Workstation Design

Design MedQC as a quiet, high-trust medical operations system. It should feel clear, restrained, and professional, not like a marketing dashboard or a generic chatbot.

Use this skill for `workstation-v4` and adjacent medical back-office pages: 质控首页概览, 病历池, 高优先级任务, 病案智能助手, 编码查询, DRG/DIP 入组, 风险洞察, 质控结果, 病历列表, and dense work queues.

## Visual Direction

- Use the current `workstation-v4/rules?tab=semantic` page as the reusable Apple-style workstation language for all `workstation-v4` pages unless the user gives a different page-specific direction.
- Use a light medical admin style: Apple-like cold light gray canvas, white glass surfaces, weak borders, soft depth, and restrained clinical data density.
- For workstation shell and rule/admin workbench pages, use the reference HTML/current rules page pattern: `#f5f5f7` canvas, white glass sidebar/topbar, Source Han Sans SC first with San Francisco/SF Pro fallback, translucent white panels, Lucide line icons, and the light-mode brand blue `#0066cc`.
- Brand blue is mode-dependent: use `#0066cc` on light content surfaces. Use `#2997FF` only for logo gradients or dark-mode-only surfaces.
- Keep the shell light by default. Do not use a dark navy sidebar unless the user explicitly requests a dark shell.
- Use blue only for primary actions, selected states, active metrics, and links.
- Use red/orange only for real risk, overdue, failed, or warning states.
- Prefer whitespace, alignment, typography, and row separators before adding cards, borders, or shadows.
- Avoid decorative blobs, bokeh, gradient orbs, large hero art, cartoon robots, and Apple/macOS visual language.
- Do not put cards inside cards. Repeated objects can be cards; whole page sections should usually be surfaces or bands.
- Use lightweight glass on major workbench shells only: `background: rgba(255,255,255,.82-.90)`, `backdrop-filter: blur(18px)`, `border: 1px solid rgba(0,0,0,.08)`, and hover shadow around `0 2px 12px rgba(0,0,0,.10), 0 6px 22px rgba(0,0,0,.075)`.
- Micro-interactions should feel deliberate: 250-300ms cubic-bezier transition, `translateY(-2px)` for large panels, and subtle `translateX(1px)` for sidebar nav.

## Apple Workstation Language

This is the default shared language for `workstation-v4`, extracted from the current `workstation-v4/rules?tab=semantic` implementation.

### Shell

- Page canvas is always cold light gray: `#f5f5f7`. Do not mix warm white, beige, cream, or tan backgrounds into dashboard/workbench pages.
- Sidebar and topbar are white glass: `rgba(255,255,255,.82-.90)` plus `backdrop-filter: blur(18px-20px)` and a weak `rgba(0,0,0,.08)` border.
- Main content should sit on the gray canvas with large white glass panels. Avoid dark blocks, colored bands, and heavy gradients.
- Default shell width: sidebar around 220px; topbar around 52-56px. Keep the workspace dense enough for hospital operation workflows.

### Color System

- Primary blue: `#0066cc` for light mode buttons, active tabs, links, selected menu text, primary numbers, and focused states.
- Logo-only blue gradient: `#2997ff -> #5ac8fa`; do not use `#2997ff` as the default light-page action blue.
- Text:
  - Primary: `#1d1d1f`
  - Secondary: `rgba(29,29,31,.60)`
  - Subtle: `rgba(29,29,31,.38)`
- Borders: `rgba(0,0,0,.08)` by default; use `.12-.14` only for hover or active emphasis.
- Risk colors are sparse: red/orange only for true risk, overdue, failed, or warning states. Do not make metadata chips a rainbow.

### Typography

- Use the app font stack: `Source Han Sans SC`, `San Francisco`, `SF Pro Text`, `SF Pro Display`, `Inter`, `PingFang SC`, `Microsoft YaHei UI`, `system-ui`, `sans-serif`.
- Page title: 28px/31px, 700, tight but not oversized.
- Section title: 17px/22px, 600.
- Table row title: 14px/20px, 600.
- Body text: 13-14px/20-22px, 500.
- Labels, badges, table headers: 11-13px, 500-600.
- Avoid large black display text inside operational panels. Data hierarchy should come from spacing, alignment, and contrast, not huge bold type.

### Glass Surfaces

- Workbench shell: 20px radius, `rgba(255,255,255,.86)`, 18px blur, 1px black-alpha border, small shadow.
- Large panel hover: increase border to `rgba(0,0,0,.14)`, use shadow `0 2px 12px rgba(0,0,0,.10), 0 6px 22px rgba(0,0,0,.075)`, translate `-2px`.
- Inner controls: 8px radius, white or low black-alpha background; do not use thick borders or saturated fills.
- Avoid nested card-on-card composition. A workbench can be one large glass panel containing header, filters, and list.

### Tables And Dense Lists

- Tables should feel like Apple admin worklists: white/light header, subtle separators, calm hover, and enough width for Chinese text.
- Prefer content-rich rows over many narrow columns. Merge low-value metadata into the main text cell as tags.
- Action buttons should be part of the row content when possible, aligned with the core item text, not isolated in a heavy fixed operation column.
- Fixed columns must keep the same background as the row hover state; avoid visible block-color mismatch on hover.

### Buttons And Chips

- Primary button: filled `#0066cc`, 8px radius, 13px/600, subtle blue shadow.
- Secondary button: white/transparent with low black-alpha border, 8px radius.
- Chips/tags should be low-saturation and mostly neutral. Use blue-gray for executable/mapped-rule metadata, gray for dependency type, orange/red only when the state is a real warning.
- Icons use `lucide-vue-next`, 14-18px, stroke 2-2.2, inherit text color.

### Selects And Dropdowns

- Select controls and dropdown popup layers must use the same workstation font stack as the page, with `Source Han Sans SC` first and `San Francisco` / `SF Pro Text` as fallback. Do not leave Ant Design default dropdown typography if it looks larger, heavier, or mismatched.
- For Ant Design Vue selects whose popup renders outside the component tree, assign a stable `popup-class-name` and define global popup styles.
- Dropdown popup: 10px radius, `rgba(255,255,255,.94)` background, `backdrop-filter: blur(18px)`, border `1px solid rgba(0,0,0,.08)`, shadow `0 8px 24px rgba(0,0,0,.12)`.
- Dropdown item typography: 13px font size, 20px line height, 500 weight, primary text `rgba(29,29,31,.78)`, minimum row height around 34px, horizontal padding around 12px.
- Dropdown hover: `rgba(0,0,0,.04)`. Selected item: `rgba(0,102,204,.08)` background, `#0066cc` text, 600 weight.
- Select inputs in filter/tool rows should be 34px high, 8px radius, 13px text, and visually calm. Focus should use a subtle blue ring such as `0 0 0 3px rgba(0,102,204,.08)`.

## Layout System

Use this hierarchy for workstation pages:

1. Header: breadcrumb, page title, short operational subtitle, key actions.
2. Filter/Summary: compact search/filter strip and KPI strip.
3. Priority Area: highest-value queue or risk group.
4. Details/List: dense scannable table or list for real work.
5. Insight Sidebar: rankings, risk reasons, current changes, or guidance.

Avoid huge blank chart panels. If no meaningful trend data exists, show a useful list, queue, summary, or empty state with next action.

For rule/admin workbench pages, use this hierarchy:

1. Compact page header: literal Chinese title, one-line operational subtitle, optional compact rule-type tabs.
2. Optional metric strip: 3-4 glass metric cards only when they directly orient the user.
3. Main workbench shell: one glass panel containing rule-set selection, result count, primary action, filters, and table.
4. Modal/drawer detail: examples, prompts, mapped execution rules, execution dependencies, and test output.

Do not stack decorative overview panels above dense rule lists. If a section does not help the current tab, hide it.

## Core Components

### Page Header

- Title should be literal and operational: `质控首页概览`, `病历池`, `病案智能助手`.
- Subtitle explains what the page helps users do, not marketing value.
- Keep action buttons compact and aligned right.
- Do not use oversized hero sections for back-office tools.
- Rule/admin pages should use a compact Chinese eyebrow such as `规则管理`, not English decoration like `RULE CONTROL`.
- Rule type tabs should be compact blue capsule tabs with Lucide icons and short labels. `ICD / FP / SET / SC` may be used as small technical badges only when users already understand them.

### Sidebar Navigation

- Use `lucide-vue-next` line icons plus text for `workstation-v4` sidebar navigation.
- Default shell uses a white glass sidebar, matching the reference HTML. Icons inherit item color and should be about 17px with stroke width around 2.1.
- Active state must be calm and clearly blue: `rgba(0,102,204,.1)` background, `#0066cc` text/icon, and a 3px left blue indicator. Avoid glow-heavy selected states.
- Hover state uses `rgba(0,0,0,.05)` with no dark blocks, no gradients, and no heavy shadow.
- Expanded submenu containers should be subtle light glass blocks. Do not add a vertical connector line on the left.
- Parent submenu selected/open states should use `#0066cc` or `#1d1d1f`; avoid pale-blue text intended for dark sidebars.

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
- On rule/admin pages, metric cards use glass background, subtle gradient border, Lucide icon circle, Display-weight value, and muted helper text.
- Safety boundary metrics such as `不写病历` should use red warning accent (`#FF453A`) for icon and value, while keeping the card calm.

### Priority Queue

- Prefer one grouped surface with lightweight repeated cards or rows.
- Each item should expose: patient/visit id, department, status/risk tag, time pressure, primary action.
- Keep cards small enough to scan. Do not make every patient card a large floating tile.
- One active or most urgent item may use a stronger blue accent.

### Worklist / Table

Use list-table hybrids for high-volume pages like 病历池.

Recommended columns: 患者信息, 科室, 状态, 风险标签, 入院/出院, 更新时间, 操作.

Keep row height readable, use subtle separators, and avoid narrow Chinese columns that wrap character-by-character.

### Rule Management Workbench

Use `workstation-v4/rules?tab=semantic` as the reference design for rule management and dense admin pages.

- Outer shell: one large glass panel with 20px radius, weak border, light shadow, and visible hover depth.
- Header row: left side has small eyebrow and title; right side holds rule-set selector, current result count, and primary/secondary actions.
- Rule-set selector: Lucide `Layers` icon, Chinese label `规则集`, compact select, and URL query persistence when applicable.
- Filter row: one compact query bar with search, defect level, complexity, and document type. Keep visible labels Chinese. Its select dropdowns must use the shared Apple-style dropdown popup: 13px font, 34px item height, glass background, low-saturation hover, and blue selected state.
- Table style: white/light header, subtle gray row separators, hover background `rgba(0,0,0,.025-.04)`, rule code pill, document type text/pill, and rule name as strongest row text.
- Rule table should stay compact and work-oriented. Prefer three primary columns: `序号`, `编号`, `适用文书`, and one wide `规则名称` content column. Do not show `复杂度`, `缺陷级别`, or `操作` as independent right-side table columns unless the user explicitly asks for audit-style columns.
- Put row actions inside the wide `规则名称` cell, aligned to the right of the title/description block. The layout should be: left side `规则名称 + 描述 + 标签 + 映射规则`, right side compact action buttons such as `查看结果` and `评估`. These buttons should be visually parallel to the rule title/description area, not dropped below metadata tags and not isolated in a separate fixed action column.
- Row metadata: use small Chinese semantic tags for implementation status, dependency type, data status, and mapped execution rules. Never expose raw enum strings like `ready_with_data_gap`.
- Actions: compact buttons with Lucide icons, such as `Eye` for detail/result, `FlaskConical` for test/evaluate, and `Play` for batch execution. In rule tables, row-level actions belong inside the rule content cell; page-level actions stay in the workbench header.
- Detail modal for customer rule packages should show: 客户质控点口径, 触发条件, 不触发条件, 映射执行规则, 执行依赖, 正例, 反例.
- Positive/negative examples should be realistic medical-record snippets. Do not write meta text such as `这是反例` or `备注：未分析`.
- The semantic tab should prioritize the rule list. Hide unrelated coverage/audit panels unless the user explicitly enters a coverage view.

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

### 质控规则管理

Use the rule management workbench pattern.

- Default route `/workstation-v4/rules?tab=semantic` should prioritize the rule-set selector, filters, and rule table.
- `SC 全病历质控规则` and `泸县0609质控点验证 v1` should feel like switchable rule packages, not separate pages.
- For customer rule packages, display customer-facing rule IDs and names as first-class rows, while mapped `SC/LX/CL` execution rules remain secondary metadata.
- Light rule pages should use `#0066cc` consistently for buttons, active tabs, tags, links, and primary numbers. Reserve `#2997FF` for logo gradients or explicit dark-mode surfaces.

## Interaction Rules

- Primary actions use filled blue buttons: `立即处理`, `执行分析`, `查询`.
- Secondary actions use outline or text buttons: `重置`, `刷新`, `标记稍后`.
- Chips and segmented controls should be small, calm, and data-rich.
- Loading and empty states should tell users what is happening and what they can do next.
- If a backend capability is unavailable, say `该能力待接入`; do not fake a successful result.
- Rule-set switches must update the visible list immediately and preserve state in URL query when the route already uses query-driven tabs.

## Implementation Guardrails

- Reuse existing `workstation-v4` tokens, containers, Ant Design Vue patterns, and local components where practical.
- Prefer `lucide-vue-next` for new workstation navigation, workbench, filter, and action icons.
- Do not invent a separate visual language for one page.
- Do not modify backend contracts for pure presentation unless compatibility and fallback are explicit.
- Do not add `.vue.ts` mirror files.
- Keep text UTF-8 and avoid mojibake.
- Visible enum values must be translated to Chinese. Raw enum strings belong only in hidden debug output.
- Before finishing implementation work, run at least `npm run check:encoding`, `npm run lint`, and `npm run type-check`.
- If changing shared behavior or task/result flows, also run `npm run test:unit`.
