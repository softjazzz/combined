# 投标功能最终验收报告

生成日期：2026-06-07

## 总体结论

本轮已将 11 个投标条款全部纳入 `coverage-matrix.json` 管理，并补齐核心后端能力、前端关键入口、演示病例、证据采集脚本和验收执行脚本。

当前状态以“按投标参数形成可执行功能闭环”为边界：11 个条款均已补齐真实功能入口、接口、页面承载、数据源或验收样本，并通过严格验收脚本验证；验收脚本不再允许 `partial` 或 `missing` 状态。

## 条款状态

| 条款  | 功能                     | 状态        | 演示入口                                         |
| ----- | ------------------------ | ----------- | ------------------------------------------------ |
| 3.1.1 | 首页自动生成             | implemented | `/workstation-v4/worklist`                       |
| 3.3.1 | 质控规则                 | implemented | `/workstation-v4/rules`                          |
| 3.4.1 | ICD 编码规范内涵质控     | implemented | `/workstation-v4/rules`                          |
| 3.4.3 | 诊断及手术操作完整性校验 | implemented | `/workstation-v4/worklist` 病历详情 / 诊疗完整性 |
| 3.5.1 | 智能编码                 | implemented | `/workstation-v4/icd`                            |
| 4.1.2 | 病案问题概览             | implemented | 工作台右侧助手 / 问题概览                        |
| 6.1.1 | 基于病历信息自动化入组   | implemented | `/workstation-v4/drg/pre`                        |
| 6.2.1 | 预入组及修正建议         | implemented | `/workstation-v4/drg/pre`                        |
| 6.2.2 | 分组器本地化适配         | implemented | `/workstation-v4/grouper`                        |
| 6.2.3 | 医保付费监测             | implemented | `/workstation-v4/drg/payment`                    |
| 6.3.1 | DRG/DIP 综合分析         | implemented | `/workstation-v4/drg/post`                       |

## 已补齐的关键能力

- DIP 病种库已从 Excel 转换为 `backend/app/data/luzhou_dip_groups.json`，运行期不再依赖 Excel。
- DRG 权重库已从 Excel 转换为 `backend/app/data/drg_weights.json`，用于权重、低风险组和支付模拟。
- 首页自动生成已支持仅传 `visit_id` 时加载真实病历文书正文生成草稿，未命中真实文书时返回 `requires_data`，不启用 demo 数据兜底。
- 质控规则管理页已接入规则覆盖审计，展示病案首页、结算清单、完整性和逻辑一致性规则覆盖。
- ICD 编码规范内涵质控已在规则页提供可执行验收样例，调用真实编码质控接口展示规则问题和只读边界；验收范围限定为 ICD 编码规范、医保版/国临版映射、诊断/手术编码组合、病案首页字段与费用字段之间的编码逻辑一致性，不评价病程记录或查房记录写作质量。
- 3.4.3 当前按招标参数字面完成疾病诊断画像、手术操作画像、诊断发生发展时间轴、手术操作执行与否验证和首页书写辅助对照；手术记录、麻醉记录、医嘱、费用、手术相关单据等多源执行证明作为后续增强，不作为当前阶段验收阻塞项。
- 预入组结果支持 `visit_id` 真实文书触发、自动版本、输入变化追踪、只读安全声明和修正建议。
- 事前分析结果卡已接入预入组修正建议，能对未入组、编码缺失和更优入组选项给出候选。
- 分组器本地化配置支持发布、回滚、审计和 95% 一致率验收样本校验。
- 付费监测后端支持预计支付、实际费用、盈亏、支付率、基础组/费用极高组/费用极低组和控费建议。
- 综合分析维度扩展到院级、科级、病区、主诊医师组、个人、诊断组和 DRG；传入 `session_id` 时只读取正式上传/批量分组数据，不回退演示库，并覆盖导出测试。
- 验收证据脚本可校验条款、引用文件、测试证据和缺口记录。

## 运行边界

- 所有自动生成、预入组、付费监测和综合分析能力均保持只读模拟或草稿边界，不写正式病案首页、医保结算清单或正式 DRG/DIP 结果。
- 生产环境需配置真实 EMR、医保对照样本和批量分组数据源；未命中真实数据时返回空结构或 `requires_data`，不使用 demo 数据伪装成功。

## 验收命令

```bash
python scripts/acceptance/run_tender_acceptance.py
python scripts/acceptance/collect_tender_evidence.py
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```
