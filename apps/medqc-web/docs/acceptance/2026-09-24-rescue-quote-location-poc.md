# 抢救记录原子引文坐标回填：一次性离线 POC

基线为 `ce1e125284a18193d1638879c08ca657e5f4a4c7` 已冻结的 R01 Evidence Session 与唯一一次 `qwen3.8-flash` 原始响应。本实验在后续集成树上运行，**没有修改生产代码、Prompt、模型参数、医学判据或原始模型响应，也没有再次请求模型**。脚本与含病人原文的修正副本均在 `.tmp/0910-full-audit/*-private`，不得提交。

## 问题与最小实验

原模型六项均返回 `present` 与逐字引文，但六项 `start/end` 无法从同文书回取对应引文，现有 `_parse` 因此整批拒绝为 `model_invalid_output`。主协调另行固定的精确出现次数证据显示，这六段引文各自仅在所绑定文书正文中出现一次。本实验只修改响应副本中的六组 `start/end`：

```python
position = body.find(quote)
if position < 0 or body.find(quote, position + 1) >= 0:
    raise ValueError("missing or nonunique verbatim quote")
atom["start"], atom["end"] = position, position + len(quote)
```

回填前须确认 `document_ref` 精确属于本次 Evidence Session、同一响应无重复文书、`quote` 是非空且不超过160字的原样字符串、原 `start/end` 是整数且非布尔。不得裁剪/标准化引文、跨文书找最近文本、在多次出现时择一。`absent/unknown` 原子原样保留；之后仍调用生产 `_parse` 完成全部原合同校验。真实源正文与本次发送给模型的正文相同，均为765字符，但该实验不据此假设以后每份病例脱敏前后均相同。

脚本 `.tmp/0910-full-audit/phase-a-rescue-quote-location-poc-private.py` 的 10 个合成反例均拒绝：未知或重复文书、相同引文两次出现、相互重叠的重复出现、无逐字匹配、近似但不相同文本、空引文、超过160字引文、非字符串引文、非整数/布尔坐标。这些仅是格式安全边界，不能替代真实病例医学验收。

## 固定响应回放结果

原响应文件字节未变；修正副本写入 `.tmp/0910-full-audit/phase-a-rescue-location-corrected-20260924-private.json`。现有 `_parse` 接受修正副本，但它对时间原子继续执行独立语义校验：模型所给时间引文不满足其明确时间标签格式，`rescue_time` 被降为 `unknown`，其余五项为 `present`。同一固定 Evidence Session 经既有 `prepare → aggregate/Finalizer` 回放后，R01 仍为 `data_gap / required_field_missing`；公开事实的 `failure_kind` 从 `model_invalid_output` 变为空，剩余未知字段仅为 `rescue_time`。所以 **唯一引文定位仅消除了这次坐标格式失败，并未使 R01 恢复为合规或证明临床判定正确**。

实验命令 `python -X utf8 .tmp/0910-full-audit/phase-a-rescue-quote-location-poc-private.py` 退出码 0；记录在 `.tmp/0910-full-audit/phase-a-rescue-location-poc-20260924-private.json` 和独立全链产物 `.tmp/0910-full-audit/phase-a-rescue-location-chain-20260924-private.json`。固定响应在本机回放一次，真实新增模型调用为 0。

## 供后续单独决策的最小方向

若要调整合同，可只在抢救原子解析边界对**坐标错误但引文唯一逐字命中当前绑定文书**的 `present` 原子回填位置，其余情况继续拒绝；保留时间标签、姓名/职称关联和最终状态的现有校验。应另立行为修复任务，先冻结有效、无效、多匹配、脱敏差异和医学正负样本，再评估调用量、状态与证据变化。本 POC 不授权把生产解析器改成宽松模糊匹配，也不能作为阶段 A 已通过临床验收的证明。

主协调独立复跑同一POC，退出码0：6项坐标回填、10个反例拒绝，时间仍unknown、最终资料不足，真实新增模型调用0。接受实验结论，不将其视为生产修复。
