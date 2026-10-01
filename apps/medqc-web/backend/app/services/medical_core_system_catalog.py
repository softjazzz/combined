"""医疗质量安全核心制度固定字典；CORE-* 为项目内部 ID，不是官方编码。"""

CORE_SYSTEM_SOURCE_URL = "https://www.nhc.gov.cn/yzygj/c100068/201804/42ab2552298047679cd6ec733f233862.shtml"
_NAMES = (
    "首诊负责制度", "三级查房制度", "会诊制度", "分级护理制度", "值班和交接班制度",
    "疑难病例讨论制度", "急危重患者抢救制度", "术前讨论制度", "死亡病例讨论制度",
    "查对制度", "手术安全核查制度", "手术分级管理制度", "新技术和新项目准入制度",
    "危急值报告制度", "病历管理制度", "抗菌药物分级管理制度", "临床用血审核制度", "信息安全管理制度",
)
CORE_SYSTEMS = tuple({"id": f"CORE-{index:02d}", "name": name} for index, name in enumerate(_NAMES, 1))
CORE_SYSTEM_IDS = frozenset(item["id"] for item in CORE_SYSTEMS)
