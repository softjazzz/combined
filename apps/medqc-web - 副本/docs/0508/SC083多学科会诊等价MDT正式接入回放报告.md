# SC083 多学科会诊等价 MDT 正式接入回放报告

## 范围

- 本轮将 SC-083 注册到正式 applicability gate registry，并做只读回放验证。
- 不接页面，不写正式 QC 结果表，不开放程序化 confirmed。
- 本地 CDM 未发现专门 `mdt_record` 表；证据从 `consultation_record`、`presurg_discussion`、`daily_course_record`、`senior_course_record` 聚合。

## 总览

- 回放病历数：16
- code gate 通过数：2
- mdt_evidence_status 分布：`{"level4_applicability_data_gap": 13, "level4_applicable_mdt_equivalent_evidence_accepted": 2, "level4_not_applicable_by_code": 1}`
- 建议分流分布：`{"data_quality_gap": 13, "rejected_by_system": 3}`
- MDT 等价证据 accepted 数：2
- 程序化 confirmed 数：0

## 关键口径

- `consultation_record` 可能包含多科室证据：既可能标题为“多学科会诊记录”，也可能正文中出现多个科室意见。
- 客户已确认：多学科会诊/多科会诊/联合会诊可作为 MDT 等价证据。
- 普通单科会诊不能替代 MDT；同一术前场景下多个不同专科会诊可聚合为 MDT 等价证据。
- 四级手术编码只能证明 SC-083 适用性，不能证明缺陷成立。
- `level4_applicable_mdt_evidence_missing` 最多进入二轮候选，不得程序化 confirmed。

## MDT 等价证据 accepted 样本

- `2142472` / 张泽芳：departments=['内分泌科', '康复科', '心内科', '神经内科', '骨科']；quote=2、2型糖尿病 3、高血压 4、陈旧性脑梗死 5、心律失常 6、低钾血症 7、腔隙性脑梗死 8、颈动脉斑块 9、肾功能异常，患者血压低,心率快,给予补液,完善检查，邀请相关科室术前评估.患者心电图异常，给予完善心肌酶谱检查，低钾，给予补钾治疗。已完善颅脑cta检查，再次邀请神经内科、心内科会诊。 医生签名：段超 周雨
  周雨
  张北南副主任医师查房记录
  :张北南副主任医师今日查房， 患
- `2214679` / 田正群：departments=['妇科', '康复科', '胸外科', '麻醉科']；quote=助治疗。胸外科医师会诊意见:  
   医生签名:
  术前讨论记录
  魏欣
  申威科主任讨论地点：:妇科医生办公室
  银娟副主任医师，杨晶主治医师、魏欣主治医师，刘敏住院医师，麻醉科李世元主任医师，刘隆平护士长，王燕护士病史汇报：:魏欣主管医师汇报病史：患者为61岁女性，主诉发现外阴肿物脱出半年。查体嘱患者用力屏气时见宫颈位于处女膜内约0.5cm，阴道前壁膨出于处女膜外阴道内见较多黄色分泌物，阴道壁充血。

## 四级适用但讨论证据不足样本

- 本轮未发现四级适用但讨论证据不足样本。

## 是否建议生产接入

- 建议生产接入第一阶段：SC-083 gate 仅做 metadata、`rejected_by_system` 和 `data_quality_gap/pass_to_second_gate` 分流。
- 多学科会诊/多科会诊等价 MDT 证据命中时输出 `rejected_by_system`，表示“不构成未 MDT”。
- 仍不得开放程序化 confirmed；缺 MDT 证据只能进入二轮候选。
