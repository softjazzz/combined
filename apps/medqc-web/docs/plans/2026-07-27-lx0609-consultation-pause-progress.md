# LX0609 会诊族 020/023 暂停进度说明

日期：2026-07-27

状态：暂停，不提交、不推送

范围：LX0609 会诊族原生链，重点为 LX0609-020 / LX0609-023

## 1. 暂停结论

会诊族 020/023 目前投入产出比偏低，先暂停继续开发。

当前不建议继续扩大为会诊 Evidence Graph、Action Event Engine 或更多候选来源建模。已完成的工作可以作为诊断 checkpoint 保留，但 020/023 不应按当前结果宣称生产收口。

核心原因：

- 020/023 属于跨文书语义关联，模型输出仍存在正向结论漂移；
- Fast10 三轮验证未达到启用前稳定性门槛；
- 继续深挖会消耗大量时间，短期客户演示收益不如先处理其他更确定的质控点和 UI/证据展示问题。

## 2. 已确认业务口径

本轮已与业务方确认以下口径：

1. 020/023 可以走原生链，但不稳定分支不能输出确定不合规。
2. `evaluation_unknown` 必须在前端归入“AI建议复核”，不能混入“不合规”统计。
3. 020/023 的确定不合规只允许非常收窄的场景：
   - 020：明确会诊建议需要执行，且后续没有任何对应结构化执行证据，也没有具体执行记录；
   - 023：已有落实记录，但只写“遵会诊意见执行 / 已按建议处理”等泛化表述，未记录具体动作。
4. 只有结构化医嘱，不能直接判 020/023 合规。
5. 只有病程具体描述，但没有结构化支撑，也不能直接判 020/023 合规。
6. 泛化执行：
   - 020：AI建议复核；
   - 023：确定不合规。
7. 多建议聚合：
   - 明确失败才报不合规；
   - 不确定项不得升级为不合规。

## 3. 当前代码 WIP

当前工作区存在大量历史 WIP；本轮仅改动以下 4 个文件：

- `backend/app/core/settings.py`
- `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`
- `backend/tests/unit/test_settings_llm_env_alias.py`

本轮局部改动内容：

1. 默认启用会诊原生入口：
   - `LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True`
   - `LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True`
2. 在第二阶段执行关联中拆分两类证据：
   - 病程/查房执行记录痕迹：`specific_trace / generic_trace / copied_opinion / no_trace / unknown`
   - 结构化动作匹配：`linked_specific / linked_vague / absent / unknown`
3. 020/023 聚合逻辑收窄：
   - 低置信、模型 unknown、只有医嘱、只有病程、正向合规证据不稳定时均进入 `evaluation_unknown`；
   - 023 的泛化执行仍可形成确定不合规；
   - 020 的明确无任何执行证据仍可形成确定不合规。
4. 补充或调整单元测试，避免旧测试继续把“病程具体动作”当作确定合规。

注意：当前 WIP 尚未提交；暂停期间不要基于这些改动直接发布。

## 4. 已完成验证

### 4.1 聚焦单元测试

命令：

```bash
cd backend
python -m pytest tests/unit/test_luxian_0609_native_consultation_episode_execution.py tests/unit/test_settings_llm_env_alias.py -q --confcutdir=tests/unit
```

结果：

- 133 passed
- 1 个既有 Pydantic deprecated warning

### 4.2 主链相关局部测试

命令：

```bash
cd backend
python -m pytest tests/unit/test_luxian_0609_mainline_services.py tests/unit/test_luxian_0609_native_consultation_execution.py tests/unit/test_luxian_0609_executor_registry.py tests/unit/test_luxian_0609_runtime_manifest.py -q --confcutdir=tests/unit
```

结果：

- `test_luxian_0609_mainline_services.py` 通过；
- `test_luxian_0609_runtime_manifest.py` 通过；
- `test_luxian_0609_native_consultation_execution.py` 大量失败；
- `test_luxian_0609_executor_registry.py` 有失败。

解释：

- 失败主要来自另一套历史会诊执行器 `native_consultation_execution.py` 的旧预期，与本轮 `native_consultation_episode_execution.py` 新口径不一致；
- `executor_registry` 失败包含当前工作区其他 WIP 的影响，不宜在本轮会诊任务里扩大修复；
- 本轮没有继续修旧会诊执行器，避免范围失控。

## 5. Fast10 三轮验证结果

使用正式普通会诊选择器前 10 例，只读执行原生会诊链；模型参数固定为：

- `temperature=0.0`
- `top_p=1.0`

第一次完整三轮结果：

- 病例数：10
- 最终客户风险等级稳定病例：9 / 10
- 稳定率：90%
- 确定不合规稳定性：100%
- 总调用：51 次
- 总 token：130,761

关键漂移：

- `case-08`
  - 第 1 轮：020/023 = `compliant`
  - 第 2、3 轮：020/023 = `uncertain`

处理：

- 已将 020/023 的确定合规进一步收紧为 `evaluation_unknown`，用于避免正向漂移直接影响客户结论；
- 随后启动了第二次 Fast10 三轮复测，但任务被用户暂停，临时 Python 进程已终止，未形成完整第二轮验证结论。

## 6. 当前风险

1. 020/023 真实业务准确性尚未闭环。
2. 正向合规证据仍依赖模型稳定抽取和关联，短期不宜作为确定合规输出。
3. 020/023 的不合规输出已收窄，但仍需要后续真实病例人工抽查确认误报率。
4. 当前工作树有大量历史 WIP，提交前必须只挑选本轮明确文件，避免混入无关改动。
5. 旧 `native_consultation_execution.py` 与新 `native_consultation_episode_execution.py` 并存，是技术债；但本轮不建议继续处理。

## 7. 建议后续恢复条件

只有满足以下条件时，再恢复会诊族开发：

1. 明确要投入会诊族，而不是优先处理其他确定性规则或前端展示；
2. 先固定一组 8-10 例普通会诊人工 gold；
3. 每例按 recommendation-level 标注：
   - 会诊建议是否准确；
   - 是否需要执行；
   - 对应结构化证据是否存在；
   - 病程记录是否具体；
   - 020 gold；
   - 023 gold；
4. 只基于 gold 修 prompt / 状态映射，不再增加大架构；
5. Fast10 三轮至少达到：
   - 最终客户风险等级稳定率 ≥95%；
   - 确定不合规稳定率 100%；
   - `case-05 / case-08 / case-10` 不再出现确定状态漂移。

## 8. 建议当前取舍

短期建议：

1. 暂停会诊 020/023。
2. 保留 021/022 和会诊 episode 识别能力。
3. 020/023 在客户侧只允许输出 AI建议复核或保持兼容链，避免确定缺陷误报。
4. 优先处理：
   - 当前演示病历中高频 data_gap 的来源投影；
   - 质控结果展示质量；
   - 规则 018 等客户可直接理解的结论文案；
   - 其他 Python 确定性或单次 LLM 可稳定完成的规则。
