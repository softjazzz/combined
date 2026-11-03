# PR29评审边界修复：规则级失败承接与Gateway身份解析

## 固定起点与范围

- 开发基线：`d4b08bf98e5fff2616c9c59a79761d9714cd4905`，独立分支`codex/lx0609-token-budget-p5b-20261102`，开始工作区干净。
- 目标分支仍为`codex/business-agent-integration`；本轮不移动目标分支，不合并、部署、启用开关或启动服务。
- 先用实际病程执行器和实际双模型候选构造路径复现两项失败；不能用旧CI全绿否认未覆盖边界。

## P1：病程族同次有效结果不能随单条预算失败丢弃

原族级装饰器发现任意预算错误即抛出，丢弃原生返回值；Engine只能形成整族技术失败。旧保护集只证明其他族不受影响，未证明同族兄弟规则保留。

修复在病程执行器内部维持原规则顺序、原Prompt和判定逻辑，将原循环体提为局部单规则函数（原continue对应return）。每条规则使用局部预算失败作用域：包括其内部旧catch已经吞掉的预算拒绝，都由该执行器明确生成本规则的技术结果。其余已完成结果、显示事实、用量与顺序保留，不增加调用或重跑。

公共预算账本区分“已由规则所有者承接”和“未承接”两类。已承接错误仍可被冻结保护读取，不会因返回局部结果而伪装成完整成功；只有未承接错误继续失败关闭。回调失败、非预算异常和取消不能被当成成功承接。基础设施、Engine、Binding及保存层不重新判断临床结论。

固定合成混合场景：`02-01-04`不适用、`02-01-05`合规、`01-01-02`预算拒绝。四种预算技术原因均经实际Native→Engine→Binding→Finalizer验证；前两项经Aggregator和内存SQLite Canonical保存读取后，规则、状态和原因保持一致。失败项保持技术未完成，不混入可交付临床结果。另有旧非typed入口和取消/冻结保护。

范围说明：本轮对病程族绑定了规则级承接；检查族沿此前既有分批/逐点失败处理。没有据返回状态猜测其他族的模型依赖范围。其他尚未明确绑定规则范围的旧catch仍保留保守的族级失败保护，不宣称所有族的局部失败隔离已验收。

## P2：Gateway模式不要求调用客户端持有模型端点

原能力查找不区分direct/gateway，一律匹配客户端端点；实际候选构造在gateway模式传`api_endpoint=None`，因此合法候选在发送前被误拒绝。

修复让准入预探测、最终发送检查及冻结身份解析显式传递dispatch_mode：

- direct仍核对规范化后的实际端点，不能借Profile绕过端点身份。
- gateway必须提供明确Profile，按唯一Profile、Provider和模型解析部署能力。没有Profile、错误模型或重复目录均拒绝；不按模型猜测Profile。
- Gateway继续核对自己持有的真实部署配置、能力、消息和输出预算。客户端能力有效但Gateway能力未验证时，仍为零模型发送。

回归经过正式RouteSession创建无端点候选、真实统一客户端、内存ASGI Gateway和固定HTTP应答；没有仅手工补造带端点客户端。没有取消Gateway最终准入、端点白名单、资源限制或未知请求保护，也没有添加云端兜底。

## 验证与边界

命令在`apps/medqc-web/backend`运行，使用现有offline runner主动阻断网络、dotenv、外部进程及业务数据库；仅内存SQLite和独立临时冻结目录。

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite context-budget-p5b tests/unit/test_luxian_0609_native_course_quality_execution.py tests/unit/test_llm_gateway_api.py tests/unit/test_llm_dispatch_routing.py tests/unit/test_qc_llm_client_thinking_budget.py tests/unit/test_llm_request_observation.py tests/unit/test_exam_result_model_route.py
```

新评审回归模块纳入现有`context-budget-p5b`套件，原CI步骤继续执行，不关闭或放宽门禁。结果在本轮交付记录补充；本轮未运行全后端/全前端或真实患者任务，旧Head的11961通过不冒充新Head结果。

最终本机联合命令：**771通过、0失败、0跳过**，1项既有Pydantic弃用警告。Ruff与`git diff --check`通过；只读ESLint通过。前端源码无改动，未重复完整类型检查或前端单测；提交前对暂存文本执行编码检查。新Head的远端CI须单独查看，不沿用旧Head结论。

两开关仍默认关闭。DSH真实计量、实际模型/模板/消息形态及16K真实请求尚未验收；保留原输出上限和不兼容清单，不宣称全引擎适配16K或医学质量等价。无业务库、模型服务、客户机连接；无模型调用、质控重跑、历史结果覆盖或迁移修改。
