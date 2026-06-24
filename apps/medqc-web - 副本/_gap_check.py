"""对照原始招标参数检查实现细节"""
import io

out = io.StringIO()

# 1. 首页自动生成 - 检查 (4) 类字段
with open('backend/app/services/frontpage_extraction_service.py', encoding='utf-8') as f:
    fp_src = f.read()

out.write("=== 3.1.1 首页自动生成：(4)类特殊字段覆盖 ===\n")
checks_31 = [
    ("呼吸机使用时间", ["ventilator", "呼吸机"]),
    ("ICU进出/时间", ["icu", "重症监护"]),
    ("颅脑损伤昏迷时间", ["coma", "昏迷", "颅脑"]),
    ("损伤中毒外部原因", ["injury", "中毒", "外部原因", "损伤"]),
    ("病理诊断自动编码", ["pathology", "病理诊断"]),
    ("药物过敏提取", ["allergy", "过敏"]),
    ("费用信息(6)", ["cost", "费用"]),
    ("人员信息(5)", ["personnel", "人员"]),
]
for label, keywords in checks_31:
    found = any(kw.lower() in fp_src.lower() for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

# 2. DRG 分析五级评价
with open('backend/app/services/drg/analysis_service.py', encoding='utf-8') as f:
    drg_src = f.read()
out.write("\n=== 6.3.1 DRG综合分析：五级评价维度 ===\n")
levels_63 = [
    ("院级", ["hospital_level", "院级", "hospital"]),
    ("科级", ["department", "dept", "科级"]),
    ("病区", ["ward", "病区"]),
    ("主诊医师组", ["physician_group", "主诊医师组", "attending_group"]),
    ("个人", ["personal", "individual", "个人"]),
]
for label, keywords in levels_63:
    found = any(kw.lower() in drg_src.lower() for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

out.write("\n=== 6.3.1 DRG综合分析：关键指标覆盖 ===\n")
metrics_63 = [
    ("CMI", ["cmi"]),
    ("费用消耗指数", ["费用消耗", "cost_index", "cost_consume"]),
    ("时间消耗指数", ["时间消耗", "time_index", "time_consume", "los_index"]),
    ("低风险组死亡率", ["低风险", "low_risk", "death_rate"]),
    ("平均住院日", ["los", "平均住院日", "avg_los"]),
    ("医保盈亏", ["盈亏", "surplus", "deficit", "profit_loss"]),
    ("药品耗材检查治疗占比", ["药品", "耗材", "drug", "consumable"]),
    ("导出doc/excel/pdf", ["export", "导出", "excel", "pdf", "word"]),
]
for label, keywords in metrics_63:
    found = any(kw.lower() in drg_src.lower() for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

# 3. notifications - 消息列表
with open('backend/app/routers/notifications.py', encoding='utf-8') as f:
    notif_src = f.read()
out.write(f"\n=== 4.1.2 notifications.py：{len(notif_src.splitlines())} 行 ===\n")
notif_checks = [
    ("当日问题聚合", ["daily", "today", "当日", "aggregate"]),
    ("未读状态", ["unread", "未读", "read_status"]),
    ("跳转/关联病历", ["visit_id", "record_id", "跳转", "link"]),
    ("按类型/科室过滤", ["dept", "type", "filter", "科室"]),
    ("推送/消息列表端点", ["GET", "list", "message"]),
]
for label, keywords in notif_checks:
    found = any(kw in notif_src for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

# 4. 分组器本地化 6.2.2
with open('backend/app/services/drg/config_service.py', encoding='utf-8') as f:
    cfg_src = f.read()
with open('backend/app/routers/drg_config.py', encoding='utf-8') as f:
    cfg_router = f.read()
out.write(f"\n=== 6.2.2 分组器本地化：config_service {len(cfg_src.splitlines())}行 + drg_config.py {len(cfg_router.splitlines())}行 ===\n")
cfg_checks = [
    ("版本管理", ["version", "版本"]),
    ("回滚能力", ["rollback", "回滚", "revert"]),
    ("变更记录/审计", ["audit", "change_log", "changelog", "变更"]),
    ("一致率验证", ["consistency", "一致率", "accuracy"]),
    ("地区方案配置", ["region", "地区", "local", "area"]),
    ("发布/激活", ["publish", "activate", "发布", "激活"]),
]
for label, keywords in cfg_checks:
    found = any(kw.lower() in cfg_src.lower() or kw.lower() in cfg_router.lower() for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

# 5. ICD 拼音搜索
with open('backend/app/routers/icd_search.py', encoding='utf-8') as f:
    icd_src = f.read()
out.write(f"\n=== 3.5.1 ICD编码查询：icd_search.py {len(icd_src.splitlines())}行 ===\n")
icd_checks = [
    ("拼音搜索(pypinyin)", ["pypinyin", "pinyin", "拼音"]),
    ("模糊搜索", ["like", "fuzzy", "模糊", "contains"]),
    ("手术编码查询", ["surgery", "operation", "手术"]),
    ("编码反查", ["reverse", "反查", "code_to"]),
]
for label, keywords in icd_checks:
    found = any(kw.lower() in icd_src.lower() for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

# 6. 3.4.3 诊断画像服务
with open('backend/app/services/diagnosis_surgery_profiling_service.py', encoding='utf-8') as f:
    diag_src = f.read()
out.write(f"\n=== 3.4.3 诊断/手术完整性：profiling_service {len(diag_src.splitlines())}行 ===\n")
diag_checks = [
    ("时间轴timeline", ["timeline", "时间轴"]),
    ("手术执行验证", ["surgery_verify", "手术验证", "operation_check"]),
    ("漏诊检测", ["missing", "漏", "incomplete"]),
]
for label, keywords in diag_checks:
    found = any(kw.lower() in diag_src.lower() for kw in keywords)
    out.write(f"  {'有' if found else '缺失':2s} {label}\n")

result = out.getvalue()
with open('_gap_check.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print("Done -> _gap_check.txt")
