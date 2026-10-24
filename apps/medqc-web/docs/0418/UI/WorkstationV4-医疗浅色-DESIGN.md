# Workstation 设计规范 · v7.1 液态玻璃

> 适用范围：工作台（`/workstation-v5/*`，外壳 `WorkstationLayout.vue`）下的全部页面、弹窗与抽屉
> 版本：v7.1（2026-09-27），取代 v1.0「医疗浅色」规范
> 已落地参照页：首页概览 `QCOverviewView.vue`、系统配置 `DataSyncConfigPage.vue`

新页面和重构页面只做一件事：**组合本文列出的 Token、公共类和组件**。不在页面私有样式里重新定义玻璃卡、页头、分段切换、状态胶囊、按钮、弹窗。

## 1. 视觉基调

- 关键词：苹果系统风、液态玻璃、纯蓝单色系、医疗专业、信息清晰。
- 画布：浅色光晕底（`--mq-bg-mesh`），所有内容放在半透明白色玻璃卡上。
- 颜色克制：品牌色只有一种蓝（`#0A6CFF`），**不使用紫色**；红、橙、绿只表示数据状态。
- 允许的两种“重”色块：首页的蓝色渐变主卡、深色进度圆环卡。其他页面只能用蓝色渐变主卡突出一处“当前对象”（如规则页的当前规则集），不再新增深色块。
- 只有浅色主题。

## 2. Token（唯一来源：`src/styles/tokens-v2.css`）

| 类别   | Token                                                                                                | 说明                                   |
| ------ | ---------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 品牌   | `--mq-brand-600` `#0A6CFF`、`--mq-brand-gradient`、`--mq-brand-hero`、`--mq-brand-shadow`            | 主按钮、选中态、主卡                   |
| 文字   | `--mq-text-primary` `#1D1D1F` / `secondary` `#515154` / `tertiary` `#6E6E73` / `disabled`            | 三级文字均满足 4.5:1 对比度            |
| 背景   | `--mq-bg-mesh`、`--mq-bg-subtle`、`--mq-bg-muted`                                                    | 画布、胶囊控件、分段切换底             |
| 玻璃   | `--mq-glass-bg`、`--mq-glass-bg-strong`、`--mq-glass-border`、`--mq-glass-blur`、`--mq-glass-shadow` | 卡片、侧栏                             |
| 语义色 | `--mq-{success,warning,danger,info}-{text,icon,bg,border}`、`--mq-neutral-*`                         | 只用于数据状态                         |
| 字体   | `--mq-font-family`、`--mq-font-display`、`--mq-font-mono`                                            | 苹果系统字体优先，Windows 回退思源黑体 |
| 字号   | 12 / 13 / 14 / 16 / 20 / 24 / 28，页面标题 `--mq-font-title` 32px                                    |                                        |
| 间距   | `--mq-space-1…8`（4 基数）                                                                           |                                        |
| 圆角   | 标签 999px / 控件 12px / 卡片 24px / 弹窗 26px                                                       | 按钮一律胶囊形                         |

品牌蓝同时出现在 `App.vue`、`tailwind.config.js`、`src/styles/index.css`，取值必须一致。

## 3. 字体层级

| 用途                     | 字号 / 字重                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| 页面标题                 | 32px / 700，字距 -0.03em（Windows 下中文走微软雅黑，只有常规/粗体两档，40px 粗体过于沉重，2026-09-27 起降为 32px） |
| 页面眉标                 | 13px / 600，三级文字色                                                                                             |
| 卡片标题                 | 20px / 700                                                                                                         |
| 步骤、区块小标题         | 16px / 600                                                                                                         |
| 大数值（指标卡、候选数） | 34–44px / 600–700，`tabular-nums`                                                                                  |
| 正文                     | 13–14px                                                                                                            |
| 辅助说明、表头           | 12px                                                                                                               |
| 编号、表名、代码         | `--mq-font-mono` 12px                                                                                              |

## 4. 外壳（`WorkstationLayout.vue`，所有页面自动生效）

- **没有顶栏**，也没有面包屑。页面的位置由页头的眉标说明，例如「数据与配置 · 系统配置」。
- 左侧是悬浮的玻璃侧栏：品牌行（右侧放收起按钮），加 6 组、17 个导航入口，图标全部用 `MqIconTile`。
- 侧栏底部是账号区：版本状态（`RuntimeBuildStatus`）、账号菜单（个人中心 / 账户设置 / 退出登录）、通知。
- 窗口宽度小于 1280px 时，侧栏自动折叠为 72px。
- 工作台的 antd 主题在 `workstationTheme.ts` 里定义，通过外壳内的嵌套 `ConfigProvider` 生效，不影响旧版后台。

## 5. 页面模板

每个页面先归到一种模板，再照对应的参照页或设计稿去做。

| 模板          | 适用页面                                                        | 结构                                                         | 参照                                          |
| ------------- | --------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| 概览型        | 首页、统计分析、DRG/DIP 分析                                    | 页头 → 主卡 + 辅卡 → 三/四栏指标卡 → 分析双栏                | `QCOverviewView` / 设计稿 HomeV71             |
| 列表 + 预览型 | 病历池、运行/终末病历质控、首页质控、结算清单质控、客户样本验证 | 页头（分段 + 主按钮）→ 指标卡 → 筛选栏 → 左列表 + 右预览面板 | 设计稿 PoolV71、RunningV71                    |
| 目录型        | 质控规则、自定义质控点、手术分级目录、ICD 编码查询              | 页头（分段）→ 蓝色当前对象主卡 → 筛选胶囊 + 搜索 → 表格      | 设计稿 RulesV71                               |
| 表单 / 设置型 | 系统配置、数据上传、数据管理                                    | 页头（分段页签）→ 带编号连线的步骤卡 → 高级设置卡            | `DataSyncConfigPage` / 设计稿 SystemConfigV71 |

通用规则：

- 页面根节点用 `.mq-page`，最大宽度 1440px。第一块永远是 `.mq-page-head`：左侧眉标加标题，右侧放分段切换、主按钮或范围胶囊。
- 页面内的一级切换（原 `a-tabs`）改用页头右侧的 `.mq-segmented`，原来的 `data-testid` 和权限可见规则都要保留。
- 创建、编辑、确认这类复杂流程放进弹窗或抽屉，不在页面里平铺。

## 6. 公共类（`src/styles/mq-components.css`）

| 类                                                                             | 用途                                      |
| ------------------------------------------------------------------------------ | ----------------------------------------- |
| `.mq-page`                                                                     | 页面容器                                  |
| `.mq-page-head` / `__copy` / `__actions`、`.mq-page-eyebrow`、`.mq-page-title` | 页头                                      |
| `.mq-card`、`.mq-card--padded`、`.mq-card__head` / `__title` / `__desc`        | 玻璃卡                                    |
| `.mq-inset`                                                                    | 卡内的半透明白色子容器（表单块、列表块）  |
| `.mq-soft`                                                                     | 卡内的浅灰信息块（指标摘要、弹窗摘要）    |
| `.mq-segmented`、`--sm`、`__item` + `.is-active`                               | 分段切换                                  |
| `.mq-status` + `--success / --warning / --danger / --info`                     | 带圆点的状态胶囊，默认是中性色            |
| `.mq-btn`、`.mq-btn--primary`                                                  | 原生按钮（antd 按钮已由主题统一为胶囊形） |
| `.mq-field`、`__label`、`__required`、`__hint`、`.mq-input`                    | 表单字段                                  |
| `.mq-table`、`.mq-mono`                                                        | 原生表格、等宽文本                        |
| `.mq-modal`（给 `a-modal` 传 `wrap-class-name`）                               | 玻璃弹窗                                  |

## 7. 组件与图标

- 图标只用 `MqIcon` / `MqIconTile`（`src/components/icons/`）。风格统一为：16% 浅色填充，1.6px 描边，细节线 55% 透明，需要强调时在右下角加实心徽章。新增图标要加到 `mqIcons.ts`，并补单测。
- 指标卡的结构是：图标块加标题和说明、大数值加单位、比例条加百分比；右下角可以放 7% 透明度的大号水印图标。
- 弹窗统一用页面内的 `<a-modal wrap-class-name="mq-modal">`。**不要用静态的 `Modal.confirm`**，它拿不到工作台主题。弹窗内容依次是：图标块、标题、说明、`.mq-soft` 摘要，底部两个等宽胶囊按钮（取消 / 主操作）。
- 表格表头用浅灰底，行间用 0.5px 分隔线。编号列用等宽字体，并且不换行。状态列用 `.mq-status`。

## 8. 可以做 / 不要做

可以做：

- 数值为 0 时不做强调，比例和数值都回到中性色。
- 同一份数据在不同区块里，状态和文案保持一致。
- 高密度信息优先用卡片或分组摘要，避免窄列导致中文逐字换行。

不要做：

- 不为了视觉效果修改后端接口或状态语义。
- 不新增紫色或其他装饰色，也不用深色大背景。
- 页面私有样式不复制公共类的写法，缺少的公共件应当补到 `mq-components.css`。
- 不写死颜色值（设计稿参数和 antd 主题除外），统一引用 `--mq-*`。

## 9. 响应式

- ≤1280px：侧栏折叠。首页主卡和进度卡上下排列。
- ≤1180px：表单字段两列，高级设置里的双面板改为单列。
- ≤900px：选项卡片、指标摘要都改为单列。
- 触控目标不小于 36px。

## 10. 迁移检查清单（每页）

1. 迁移前在 1440 / 1180 两个宽度各截一张图，和对应模板的设计稿对照。
2. 模板和脚本逻辑分开改：只改展示层，接口、状态和事件流不动。
3. 页面私有样式放到 `styles/<page>.css`，通过 `<style scoped src>` 引入。`.vue` 文件不超过 1200 行。
4. 保留原有的 `data-testid`，单测按新结构更新断言，功能断言不能删。
5. 跑 `check:encoding`、`lint`、`type-check`、相关单测，再截图复核，然后单页提交。

## 附录：文件映射

- Token：`src/styles/tokens-v2.css`
- 公共类：`src/styles/mq-components.css`
- antd 工作台主题：`src/components/layout/workstationTheme.ts`
- 外壳与导航：`src/components/layout/WorkstationLayout.vue`、`workstationNav.ts`
- 图标：`src/components/icons/MqIcon.vue`、`MqIconTile.vue`、`mqIcons.ts`
- 参照页：`src/views/workstation/QCOverviewView.vue`（+ `styles/qc-overview.css`）、`src/views/workstation-v4/DataSyncConfigPage.vue`（+ `styles/system-config.css`）
- 设计稿源文件：本地 `.tmp/ui-design-v71/`（不入库），包括 HomeV71、PoolV71、RunningV71、RulesV71、IconsV7、SystemConfigV71、SystemConfigModalV71
