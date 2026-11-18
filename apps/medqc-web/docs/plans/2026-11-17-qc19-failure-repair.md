# 19例批次失败的定向修复

基线：`eeea9f27c`，独立分支 `codex/qc43-audit-fixes-20261117`。

## 修复范围

- `02-01-04`：执行器已证明的闭合超期间隔可独立交付，不再因全局观察终点缺失被 Finalizer 改成技术失败。新增 `evaluation_scope=confirmed_interval`，不伪造 `horizon_date`；日期、间隔及不合规状态必须一致。没有确定超期间隔且无终点时仍为资料不足，原来源、身份、时间冲突和截断检查保持。
- 隐私包装器：识别 JSON 一层及多层转义换行后的人口学姓名；保留 JSON 结构、医疗数值及医师署名。无法识别的身份残留仍在发送前拦截。
- `08-01-02`：展示事实被拒时记录固定类别，区分字段合同、计数、必需字段、缺失字段、处方配对/一致性和终态冲突。不记录药名、正文、文书身份或原异常；不改变原判定与失败分类。
- `08-02-01` 共用正文提取器：补齐 JSON、重复键、结构、文书关联、覆盖、同文书引用及输出截断的安全诊断。只记录固定类别、阶段、尝试序号、受控结束原因、长度和解析位置。不改变严格引用或原有协议修正预算，不增加任务自动补跑。

## 隔离验证

新增 `test_qc19_failure_regressions.py`：37个合成用例。先复现缺陷及诊断缺失，再修复通过；不读取真实任务或患者材料。

后端仅运行以下直接受影响文件，退出码0：

```text
python -B scripts/run_pr8_offline_tests.py -p no:cacheprovider \
  tests/unit/test_qc19_failure_regressions.py \
  tests/unit/test_luxian_0609_privacy_demographic_name.py \
  tests/unit/test_luxian_0609_llm_prompt_privacy.py \
  tests/unit/test_luxian_0609_privacy_guard_retry_paths.py \
  tests/unit/test_luxian_0609_native_course_quality_execution.py \
  tests/unit/test_luxian_0609_discharge_result_mapping.py \
  tests/unit/test_luxian_0609_discharge_published_boundary.py \
  tests/unit/test_n10_course_body_controlled_facts.py -q --tb=short
```

上述隔离入口禁用真实配置加载、网络和非SQLite连接，使用合成模型替身。

前端 `result-normalizer.spec.ts` 50项通过；新增缺终点区间的反例修复前失败，修复后通过。保留原有带终点展示合同。

独立复审发现新增日期分支未拒绝不存在的日期，已补安全解析及前端日期真实性检查；两个前后端反例均先失败后通过。修后只复跑新增后端文件和该前端文件，未重跑其他已通过集合。复审者再次用独立AST反例确认该P2闭合，限定变更未发现剩余阻断。

## 交付限制

本轮未重启API、改配置、连接业务库、调用模型或运行真实质控，未改写历史任务、结果或快照。已有手术修复及运行期冻结文件未纳入本次提交。

不能宣称历史12条失败全部修好：部分模型输出未保留，具体字段/引文错误不能追补。新增诊断用于后续获准执行时定位；`08-02-02`严格引用及`03-02-01`证据落地校验没有放宽。
