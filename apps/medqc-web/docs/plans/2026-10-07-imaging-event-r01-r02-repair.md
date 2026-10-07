# 0910 R-01/R-02 影像事件边界最小修复

日期：2026-10-07。基线：`6fbee7ed22f948cd640e31aa955db68c408998c1`。本轮只改影像事件投影与专属回归测试，未暂存、提交、推送或重启服务。

## 复现与修复

R-01：原 `test_luxian_0609_guidance_event_execution.py` 在本轮修改前为 6 失败、5 通过。正文完整等于“CT引导下操作”的报告因为没有身份字段而未进入目标候选，混合检查时该事件被遗漏。现在只在影像报告身份为空、没有明确非目标执行科室时，允许正文/结果字段完整匹配既有纯操作标签来确认候选；不做 CT 关键词包含匹配。若其他字段还包含诊断内容，只保留候选身份，不授予纯引导豁免。既有 11 项断言未修改，全部通过。

R-02：同业务键合并时，CT/MRI 候选与明确 DR/超声等身份发生冲突，原代码直接确认 CT/MRI。新增专属回归最初为 6 失败、15 通过。现按身份字段优先、缺失时执行科室兜底，检查合并行是否存在明确非目标身份。冲突保留文书引用、取消确认及确定不适用，沿用 `event_binding` 和正式 `association_failed` 资料不足合同，不调用模型。未新增状态/框架，不改变模型引文验证。

新测试还覆盖反向主从冲突、同一行不同身份字段冲突、执行科室冲突、引导标签不得覆盖 DR 主记录、建议/历史比较不得确认本次检查、无类型明细并入合法主记录。最终新增 24 项。

## 已执行验证

在 `backend` 运行：

```powershell
python -m pytest tests/unit/test_luxian_0609_guidance_event_execution.py tests/unit/test_luxian_0609_imaging_identity_boundary.py tests/unit/test_0910_handoff_regressions.py tests/unit/test_luxian_0609_imaging_report_scope.py tests/unit/test_luxian_0609_native_exam_lab_execution.py tests/unit/test_luxian_0609_exam_lab_event_order_contract.py tests/unit/test_luxian_0609_exam_lab_course_time.py -q --tb=short --disable-warnings
```

结果：290 通过。两份修改 Python 文件 Ruff 通过，生产文件 `git diff --check` 通过。没有改旧测试断言以适应实现。

## 验证边界

- 真实模型调用为零；未向客户 PG 写入。
- 使用现有强制只读 PG 脚本、正式读取器及正式执行入口和本地空响应客户端核对事件投影。空响应会产生预期解析失败日志，不能据此宣称模型判定验收。
- 初次 30 例投影与 Claude 的 `proj-fix-private.json` 逐例完全一致，62 个已确认真实 CT/MRI 主记录保留；C09/C10/C12/C04 分别 4/3/3/4。随后补充执行科室冲突保护，最终默认权限下的只读复验进程持续无输出，已中止，没有获取新版投影结果；未重复申请审批。私有 `proj-r01-r02-private.json` 时间为 07:19，属于补充前的 30 例验证，不能冒充最终补丁的复验。父代理如需要可统一安排该一步。
- 这里验证事件身份及正式执行器对合成冲突的收口，不宣称重复模型稳定性或临床验收完成。
- 保存/API 三入口验证由父代理统一负责，本轮不修改共享集成文件。
- H-02、H-04及业务口径争议不在本轮范围。

## 文件所有权

- `backend/app/services/luxian_0609/exam_lab_fact_extraction.py`
- `backend/tests/unit/test_luxian_0609_imaging_identity_boundary.py`
- 本文档。

患者坐标、原始文书及投影明细只在原私有审计目录，不写入本文档或提交。

## 主协调最终复核

最终补丁使用同一强制只读脚本复跑30份0910病例，输出与Claude冻结投影逐例完全一致（30例、0错误、0差异），没有模型调用或PG写入。重点46项测试通过，其中影像35项、结构化证据11项；影像需求与实现的两路只读审查未发现确认缺陷。

提交门禁：编码检查、ESLint、类型检查已执行；前端全量单测启动因本机缺少`@jridgewell/gen-mapping`而中止，不计通过。ESLint脚本自带自动修复，本轮不纳入任何前端文件。真实模型稳定性仍交独立复验。
