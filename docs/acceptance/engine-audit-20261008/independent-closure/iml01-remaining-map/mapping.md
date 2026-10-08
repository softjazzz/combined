# IML01 剩余对象映射（只读，无新测试）

固定root `1958ae3bb954af7c28d0ed4f747b09913073a205`；后续294仅docs，不作为新执行证据。只读指定三源码、既有脱敏报告及合成fixture。本映射不增加通过数、不判联合检查医学归属。

| 实际规则 | 精确调用路径与剩余对象 |
| --- | --- |
| **LX0609-06-01-03** | `execute_luxian_0609_native_exam_lab_rules` → `build_handbook_ledger` → `_build_family_events("exam")` → `evaluate_report_completeness`。handbook:25–26固定exam_master/exam_item_report、exam_id；native:1933–1949将同一ledger交报告消费者。既有联合CT/MRI冻结用例可直接到达此消费者。原gap预期与既有实际compliant仍为业务合同待定，不擅自改预期或称通过。 |
| **LX0609-06-01-01** | 同一native入口；native:1938即使仅选该规则，也通过CT_REPORT_RULE=**LX0609-06-01-03**建exam ledger；native:1959 → `build_ct_review_input`（ct:93/134）→ `evaluate_ct_review`（ct:374）。可到达相同exam事件消费者，但ct:138另要求关联orders，随后要求course。原fixture只有master/report、没有orders/course；不能沿用报告完整性oracle宣称一致性也合规或完成语义验证。需先独立冻结包含orders/course的输入与预期，再按授权复验。 |
| **LX0609-06-03-02** | 同一native入口 → `build_handbook_ledger` → `_build_family_events("culture")` → `evaluate_report_completeness`；handbook:25–26固定labtest_master/labtest_item_report、test_id。不会消费同一exam-only联合CT/MRI case；共用函数不等于共用事件桶。本IML01已记录剩余只映射新labtest_subject等真实输入改变与正式交付链复验，不能挂CT/MRI口径争议。 |

**两条CT规则共享台账先验。** 同次选择时接同一ledger对象；关联、执行、排除、正式报告状态均来自同一exam事件。handbook:409和ct:138都消费association_resolved；但报告齐全与医嘱/病程一致性是不同消费者，后者另需orders/course，最终状态不能互相继承。

**原oracle索引：** `review-artifacts/iml01-closure/expected.json`，SHA256 `dbda7a2d78a57e7114ec72879b4300c7a682ae8fa2da35335e737e2fbf2ac05c`，case=`ct-mri-contradictory-modality`：exam_id=E1；主项胸部CT/modalityCT；同键报告胸部MRI/modalityMRI。既有 `fixed-8c9df71af-results.json`仅有LX0609-06-01-03：frozen data_gap / actual compliant、association_resolved=true、pending_customer_contract。未决业务对象是该同键跨模态报告是否获正式联合/分项关联合同，不是新医学判据。

**固定source blob：** handbook_exam_lab.py=`eb289d39c6cab81defe0eb1393439185f5f258ce`；native_exam_lab_execution.py=`f5d54399fbc603b235e609cd7932270f135fc4a7`；ct_order_course_consistency.py=`7488751ca6b425ead61539b68a676c00f8305e50`。均为`apps/medqc-web/backend/app/services/luxian_0609/`下固定1958源码。
