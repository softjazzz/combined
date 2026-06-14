# Codex 最小权限 LLM 运行配置方案

## 目标

在不启用 `danger-full-access` 的前提下，让 Codex 可以运行泸县 0609 质控 POC 的真实 LLM 调用。

核心原则：

- 文件权限只允许当前仓库读写。
- 网络只允许访问受控 LLM 出口。
- 不允许 Codex 获得全盘文件权限。
- 不允许把未脱敏真实病历直接发往未受控外部模型。
- POC 脚本只能写 `.runtime-logs/` 和 `docs/0602/` 这类项目内产物。

## 当前问题

当前 `workspace-write` 沙箱下，文件权限是合适的，但网络被限制，运行：

```powershell
python scripts/qc/poc_luxian_0609_trigger_gate_lab.py --visit-id LX0609_SYN_001 --execute --strategy baseline_current --output-dir .runtime-logs/qc-pack-poc
```

会出现：

- `provider_error_count > 0`
- `tokens = 0`
- `final_result_count = 0`

之前切换到 `danger-full-access` 后可以跑通，但这会同时放开全盘文件访问，风险过高，不适合作为长期方案。

## 推荐方案

### 方案 A：本地受控 LLM 代理，推荐

Codex 只访问本机代理：

```text
http://127.0.0.1:8787/v1
```

代理再访问真实模型服务：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

Codex 权限：

```yaml
filesystem:
  mode: workspace-write
  writable_roots:
    - D:\LLM\LX888\apps\medqc-web
network:
  allow:
    - 127.0.0.1:8787
  deny:
    - '*'
```

项目环境变量：

```env
LLM_API_ENDPOINT=http://127.0.0.1:8787/v1
LLM_MODEL=qwen3.5-35b-a3b
LLM_TIMEOUT_SECONDS=120
LLM_ALLOW_MOCK_WHEN_UNCONFIGURED=false
```

代理职责：

- 从安全位置读取真实 `DASHSCOPE_API_KEY`，不把密钥暴露给 Codex。
- 只允许 `/v1/chat/completions` 这类必要接口。
- 只允许模型白名单，例如 `qwen3.5-35b-a3b`。
- 记录请求哈希、token、耗时，不记录完整病历正文。
- 可选：对非 `LX0609_SYN_%` 的 visit_id 拒绝请求，防止真实病历外发。
- 可选：对患者姓名、身份证、电话、住址做二次脱敏。

优点：

- Codex 不需要外网权限。
- Codex 不持有模型 API Key。
- 可在代理层做审计、限流、脱敏和样本白名单。

### 方案 B：网络 allowlist 直连 DashScope

Codex 仍使用 `workspace-write`，但网络只允许：

```text
dashscope.aliyuncs.com:443
```

项目环境变量：

```env
LLM_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-35b-a3b
LLM_TIMEOUT_SECONDS=120
```

不推荐作为长期方案，因为：

- Codex 进程仍能直接访问模型服务。
- API Key 仍在 Codex 可读环境中。
- 缺少统一审计和脱敏关口。

### 方案 C：完全离线 Mock，仅用于机制测试

不访问外部 LLM，只跑 Trigger Gate、规则映射、客户点聚合。

适用场景：

- 验证 `not_applicable/data_gap/pass_to_llm` 是否正确。
- 验证样本池和 golden answer 是否能被读取。
- 验证脚本不会写正式业务数据。

不适用场景：

- 验证 LLM 真实判断能力。
- 验证 prompt、分桶、fallback、状态归一化的真实效果。

## POC 运行建议

### 1. 先跑 dry-run

```powershell
python scripts/qc/poc_luxian_0609_trigger_gate_lab.py --visit-id LX0609_SYN_001 --dry-run --strategy baseline_current --output-dir .runtime-logs/qc-pack-poc
```

要求：

- 不调用 LLM。
- 生成 gate 报告。
- 能区分 `pass_to_llm / not_applicable / data_gap`。

### 2. 再跑真实 LLM

只在方案 A 或方案 B 生效后执行：

```powershell
python scripts/qc/poc_luxian_0609_trigger_gate_lab.py --visit-id LX0609_SYN_001 --execute --strategy baseline_current --output-dir .runtime-logs/qc-pack-poc
```

通过信号：

- `provider_error_count = 0`
- `tokens > 0`
- `final_result_count > 0`
- golden answer 可以和系统结果对照。

## 不建议的方式

不要把 Codex 切到：

```text
danger-full-access + unrestricted network
```

原因：

- 文件权限过大。
- 网络出口过大。
- 真实病历、规则、密钥和日志都可能被同一进程访问。
- 不利于后续向客户解释安全边界。

## 迁主干前的安全门槛

在把 Trigger Gate、状态归一化、客户点聚合迁入正式质控主干前，应满足：

- LLM 调用必须走受控代理或明确网络 allowlist。
- API Key 不由 Codex 直接持有。
- 正式真实病历不得直接外发到未受控模型。
- POC 只能使用 `LX0609_SYN_%` 合成样本或明确脱敏样本。
- 输出报告不得包含 `raw_response`、`prompt`、`embedding` 或未经脱敏的大段病历原文。

## 当前建议

短期：

1. 继续用 `workspace-write` 跑 dry-run 和本地逻辑验证。
2. 搭一个本地 LLM 代理，Codex 只访问 `127.0.0.1:8787`。
3. 代理只放行 `LX0609_SYN_%` 合成样本的请求。

中期：

1. 把 Trigger Gate 的确定性部分迁入主干。
2. 把 `data_gap / not_applicable / uncertain / non_compliant / compliant` 统一成正式状态枚举。
3. 把客户点聚合从旁路脚本抽象为可测试服务。
4. 再用受控代理跑全 10 份合成样本和后续真实脱敏样本。
