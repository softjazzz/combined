# 0916 A3 当前版本正式回读记录

## 范围与结论

2026-10-06，在D实际工作区`b5fb15f76`时点（包含既有未提交005/006实现），完成显式验收启动、真实认证、一个010正式整包任务、PG保存及四例页面只读回读。列示主链源码另存私有快照，执行到进程退出逐字未变；不以HEAD代替全部实际源码。正式构建声明`available=false`，仅测试，不是客户发布身份。

启动修复及授权见[最小启动控制任务](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-acceptance-startup-control.md)。最多2正常任务/16次generate的上限没有扩大；保守按POST次数计，已提交2次，不再自动补提012。临床预期、病例原件/副本、启用与批准状态保持。

## 失败留痕与实际预算

第一次正常认证POST010返回500：主协调私有SQL护栏误把`rule_count`当独立INSERT参数，实际由任务`summary_json`持有。失败发生在批任务INSERT执行前，不是0916规则判定失败；仅新增验收run并绑定`creation_failed`，job及模型均0。保留v1脚本/响应/SQL产物，不删除或改成成功。

纠正护栏后只再提交一次010：新增1个leaf job、无parent，4例×32规则。累计2个新run（1 creation_failed、1 bound），1个真实批任务，4 generate、4 provider attempt、4实际HTTP请求，重试0；不是原拟的2任务/256计划对。私有护栏不是业务代码修改，未替换模型、Worker、保存或认证函数。

Python3.10 await挂起与失败帧复用曾使私有profile计数错误；独立AST合成证伪后，按版本识别挂起并强引用帧。3.10/3.11成功及连续失败attempt的第17次均阻断，响应等价。合成检查不计真实模型调用。正式运行未触发模型/SQL阻断，无PG DDL、CDM/缓存/旧任务/旧答案写入。

## 正式交付与页面

主协调调用当前纯合同校验器，并由独立审查另按四`record_ref×001..032`重建计划：128结果、0失败，唯一键128；缺失、重复、越界均0。任务`completed`，病例成功4/失败0，规则完成128/失败0。各临床状态仅为引擎结果，不代表本批人工验收了32条。

010的四行认证API比较均`same`；四例×010/012的八个原生结果，与旧冻结程序投影的状态、原因、事实、证据、定位、建议及诊断字段精确一致。010为`compliant/case_characteristic_present`，012为`compliant/first_course_required_sections_present`。012仅为010整包中的结果，未开展本次独立012正式运行。

主协调反查[0916验收投影](D:/LLM/LX888/apps/medqc-web/backend/app/routers/rule_validation.py:123)，再逐字段验证API公开投影与PG一致；`conclusion`映射findings、`customer_display_facts`映射decision_facts。API有意不公开diagnostics，不称全部内部原生字段均经API回传。浏览器通过3102代理到本进程8002，既有账号正常登录，最新job、四行一致及四例事实/证据/建议均回读；未提交case_review、验收结论或上线批准。首张截图因滚动取景空白保留为无效证据，回到顶部后的v2截图有效。

正常TCP/lifespan=on，版本200绑定实际PID24040，未认证验收请求401。未修改其他任务的8001。正式进程与临时前端验证服务器随后关闭，启动修复的68项聚焦测试及编码/lint结果保留；不补算临床通过。

## 成本实测与独立问题

实际provider参数四次一致：`qwen3.8-flash`、temperature=0、top_p=1、max_tokens=8192、enable_thinking=true、thinking_budget=256；allow_length_retry=false。这是业务模型，不是子代理Sol模型。

总Token **20,487**（四例分别4795/5453/5486/4753），累计模型API时间**86.848秒**。HTTP提交至终态回读**34.812秒**，PG started→finished约**27.769秒**；并发累计API时间与壁钟时间不可互填。这是整包成本，不拆成010/012独立规则成本，也不声称两次运行的稳定性/准确率。

进程退出后的独立只读PG查询证实：四个精确event均保存，事件Token合计20487；job的`total_tokens`和`total_processing_time`却为0。主协调用同产物及实际源码反推确认：[worker摘要](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/batch_worker.py:224)未传两个顶层统计字段，[保存层](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:5022)缺省写0，不是保存层丢弃已传数值。该问题单列后续最小修复，不混入启动提交，不覆盖已保存任务。

## 产物与剩余门禁

私有目录：`C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/`，均忽略且不提交患者材料：

- `20261006-010012-formal-tcp-private.py/json`：首次500、0job/0模型。
- `20261006-010-formal-tcp-v2-private.py/json`：正式任务、完整响应/SQL、实际源码与进程退出核验。
- `20261006-a3-offline-result-audit-private.py/json`：主协调纯文件合同、八目标和API公开投影核验。
- `20261006-a3-postflight-private.py/json`：两run/一job/四event的进程退出后PG只读核验。
- `20261006-a3-page-visible-v2-private.json/jpg`：四例完整页面状态及有效截图；旧截图不作证据。

运行前/后原件完整行、四副本文书ID/冻结结构化补丁及八旧工程答案均未变，不扩大为副本全部字段的逐列复核。仍缺真实缺项等覆盖、独立临床预期与签认、正式构建/逐规则发布配置；012独立当前正式运行、本批真实部分失败运输验收和成本统计修复未完成。008收益门禁、015/016关联及最早位置争议保持。32条仍为9本轮专项+2历史专项+3历史实验+18整包/审计，不新增临床验收或上线批准数。
