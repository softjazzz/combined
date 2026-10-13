# R-03 讨论记录显式字段证据修复

2026-10-07，基线 `57b863d2b328b2d93b004ffb6e49da55be76d804`。工作区修改，未提交、重启或部署。

## 问题与边界

独立验收交接指出：`presurg_discussion` 证据预设 `field_path=discuss_staff`，但原文仅有 `host_summary` 时，补齐会把小结写成摘录却保留人员字段坐标。该问题在正式 Finalizer 无预设讨论字段的原始观察中未触发，不能宣称已在真实患者或生产中发生。本轮只用合成原文，未调用真实模型、读取病例或写入 PG。

## 最小修复

只修改 `customer_evidence_enrichment.py`：讨论摘录选择接受已有字段约束，显式坐标只允许读取同名白名单文本；字段缺失、空白、非字符串或不属于可引用内容时不补摘录。既有文书 ID 零匹配/重复匹配保护继续生效。显式讨论字段优先于规则偏好字段，防止偏好重写现有坐标。

没有显式坐标时仍按原正文、小结、人员字段顺序选择。04-01-03 没有显式坐标时的 preferred_source_fields 既有行为不变，包括字段缺失提示及旧 v2 兼容分支；本修复不改证据标签或临床状态。已有非空摘录保持原样，不将本轮说成历史保存结果修复/清洗。

新增 `test_luxian_0609_discussion_evidence_field_binding.py`：17 项覆盖显式字段存在/缺失、空白/非文本、标题/模板/未知坐标、重复文书 ID、偏好优先级、已有摘录保持，以及真实兼容聚合入口与授权摘录读取。

## 红绿与链路证据

1. 初始两项红测试分别覆盖指定字段缺失及有值，均错误取得 host_summary，`2 failed`。
2. 修复后新测试 `17 passed`。Claude 原始合成探针 `h03b-probes-private.py` 情形 E 返回原 discuss_staff 坐标、无摘录；A/B/G 保持原摘录，C/D/H 不产生内容，F 保持缺失字段提示，无 repr 泄露。
3. 聚焦五文件合计 `50 passed`：新测试17、讨论内容10、记录时间3、MDT17、正式讨论证据三入口往返3。既有集成测试走执行器（固定替身输出）→binding→正式 Finalizer→隔离 SQLite 保存→latest/批详情 API，覆盖合规/不合规/数据不足；本轮未改其断言。
4. 兼容覆盖为 Aggregator（无 ReducedDecision）→legacy adapter→enrichment→文书组装/授权摘录，显式字段缺失不偷换，有值返回人员原文。
5. Ruff 对修改模块和新测试通过。初次受限环境聚焦运行在 MDT 阶段停滞，主动中断，没有记录为通过；在授权普通 D 盘执行环境重跑，50项耗时7.02秒全部通过。

复核命令（backend 目录）：

```text
python -X utf8 -m pytest -q -p no:cacheprovider --disable-warnings --timeout=25 tests/unit/test_luxian_0609_discussion_evidence_field_binding.py tests/unit/test_luxian_0609_discussion_evidence_content.py tests/unit/test_luxian_0609_evidence_record_time_source.py tests/unit/test_luxian_0609_mdt_freeze.py tests/integration/test_luxian_0609_discussion_evidence_roundtrip.py
python -m ruff check app/services/luxian_0609/customer_evidence_enrichment.py tests/unit/test_luxian_0609_discussion_evidence_field_binding.py
```

未运行全量测试；无真实模型验证、PG正式任务、浏览器验证或历史证据清洗。工程修复待协调者复核，不等于生产或临床验收。
