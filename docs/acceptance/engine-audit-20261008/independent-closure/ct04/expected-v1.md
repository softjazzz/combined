# CT-04 独立静态附录

仅冻结附录，不执行、不改生产。已有 CT-03 28 组预期保持，SHA256 c92061e62c1d0049f4d68ea007e774cb43ef54c81672289dba78134afe29ad9e。

根报告的既有反例：入院 6/1 08:00、强不明确病程 6/2 09:00 尚未满七天，6/8 有任意正文讨论行。native/reduced 为 NA/trigger_absent_complete，公开旧 check 因 uncertain_record_times=[]、discussion_count=1 被要求 count0，退 technical_error。此现象来自根/owner 报告，本组未执行复现。

静态 mapping 阅读显示 NA 分支当前确为 `not records and discussion_count == 0`；CT-04 预期只将已通过 sanitizer 的非负整数讨论计数放行到空成熟时间的旧 check NA。非空成熟时间不允许 NA，C/NC 与实际讨论计数仍对应。CT-02 pure time gap、CT-03 body gap 仍仅 data_gap；scope 仍 uncertain；成熟 check 的缺时摘要仍仅 C/NC 且需非空成熟时间。

正文存在、缺失、空白、非字符串均不能把尚未成熟强触发变成 body gap。本附录保护已满七天成熟与空正文的 CT-03 gap，不引入 CT-01 语义判断。无成熟时间且讨论数正数时应保留实际行数，不能以删事实绕过合同，也不能写成“未见讨论”。

静态读取时 HEAD 为 81fe8fed3027ea7f636014fd59237819138f7f9c，mapping 已含进行中的 CT-03 未提交条款；这不是 CT-04 固定修复源码。正式 target_commit 未定，等待 owner 提交与根授槽。12 个 native 场景、15 个明确公共组合及非法计数/字段矩阵见 expected-v1.json。当前执行/通过数零。
