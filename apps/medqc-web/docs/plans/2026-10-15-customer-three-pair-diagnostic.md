# 客户机三项失败定向诊断

任务 `39248038-b961-418f-8ae3-bcdb9ebffed3` 已保存 9 份结果，3 份失败，自动补跑达到 3 次上限。失败规则为 05-01-03（model_invalid_output）、03-01-04（model_transport_error）、02-01-02（model_parse_error）。这些原因码不足以确认具体异常，客户库中未查到对应 HTTP 异常观测记录。

独立脚本 `backend/scripts/diagnose_failed_rule_pairs.py` 从该任务读取失败配对，严格限制为已知的三个配对，逐对调用正式 `evaluate_running_final_bundle_input`，仅选择该对的一条规则。保留规则内部重试，不追加批次重试，不创建任务、不更新临床结果。沿用任务冻结评价日，检查冻结模型配置及版本，使用当前持久化病历包和当前只读证据源。因此这是定向重新验证，不是原始输入的逐字回放；串行执行也不能复现原批次并发负载。

脚本以 Python 异常事件捕获已被执行器吞掉的异常，输出相对代码路径、函数、行号、异常类型及数字 HTTP 状态码，不读取异常文字或局部变量。HTTP 观测替换为本进程内存存储，仅输出受控状态类别和耗时；常规应用日志与标准输出在本进程静默，病例使用 C01–C03 别名。所有本进程 PostgreSQL 新连接强制只读。该措施不修改客户正在运行的服务或数据库配置。

无需覆盖应用代码、重启或构建新包。将脚本复制到客户机 `D:\medqc\diagnose_failed_rule_pairs.py` 后运行：

```powershell
py -3.10 "D:\medqc\diagnose_failed_rule_pairs.py" `
    --backend "D:\medqc\medqc-web-customer-R26.2\backend" `
    --output "D:\medqc\failed-pairs-diagnostic.jsonl"
```

本地验证：12 项合成单元测试通过（精确配对、异常吞掉后的定位、脱敏、只读连接设置、三项编排及单项异常后继续），Ruff、编码检查、前端 ESLint 通过。未运行真实模型、未连接客户库，未运行前端全量测试和类型检查（没有前端变更）。客户机实测结果待收集，不代表三项错误已修复。
