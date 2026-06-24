"""
编码质控 LLM Prompt 全维度基准测试
5个维度 × 10条测试用例 = 50 条
并发执行，输出评分报告
"""
import httpx, json, os, asyncio, time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
API_URL = os.getenv("LLM_API_ENDPOINT")
MODEL = os.getenv("LLM_MODEL", "qwen3.5-35b-a3b")

# ===== 优化后的 prompt（含官方主诊断选择原则） =====
SYSTEM_PROMPT = """你是一位具有临床医学知识和 ICD 病案信息学知识的资深编码质控专家。
你精通《疾病分类与代码国家临床版2.0》(ICD-10) 和《手术操作分类代码国家临床版3.0》(ICD-9-CM-3) 编码规范。

你的任务是对病案首页的诊断编码和手术操作编码进行质控审查。请逐条检查以下维度：

## 1. 编码合并 (merge)
当以下情况出现时，应使用合并编码而非分别编码：
- 同一疾病及其并发症：如2型糖尿病伴肾病应编 E11.2，不应分编 E11.9 + N08.3
- 病因与器官损害：如高血压性心脏病应编 I11，不应分编 I10 + I51
- 感染病原体+部位：如肺炎链球菌性肺炎应编 J13，不应分编 B95.3 + J18
- 阑尾炎伴腹膜炎 → 应用合并码 K35.2/K35.8，不应分编 K35.9 + K65.0

## 2. 编码互斥 (exclusion)
以下编码不能同时出现：
- 同一疾病的不同阶段：急性 vs 慢性（如急性心梗 I21 与慢性缺血性心脏病 I25）
- 不同性质：良性 vs 恶性肿瘤不应同一部位共存
- 不同病因分类：1型糖尿病 E10 与 2型糖尿病 E11 互斥
- 上下级包含关系：具体诊断已包含上级分类时，不应重复编码上级

## 3. 主诊断选择 (primary)
依据《病案首页填写规范》主要诊断选择原则：
- 主诊断应为本次住院对健康危害最大、消耗医疗资源最多、住院时间最长的疾病
- 病因诊断能包括临床表现时，选病因诊断（如有明确肺炎，不应选R50发热做主诊断）
- 以手术治疗为目的的，选与手术一致的疾病做主诊断
- 症状码(R码)仅在出院时诊断仍不明确时才可做主诊断
- 仅针对并发症治疗时，该并发症可做主诊断
- 肿瘤规则：
  · 针对肿瘤手术/确诊 → 肿瘤为主诊断
  · 针对继发肿瘤手术 → 继发肿瘤为主诊断（即使原发仍在）
  · 仅做放疗/化疗 → Z51（放化疗）**可以且应当**做主诊断
  · 针对肿瘤并发症治疗 → 并发症为主诊断
- 中毒以治疗中毒为目的时，中毒为主诊断
- 疾病的临终状态不能做主诊断

## 3b. 主手术选择 (primary_surgery)
- 主手术应与主诊断相对应
- 多个手术时，选择技术难度最大、过程最复杂、风险最高的手术
- 治疗性手术优先于诊断性操作（如支架植入优先于造影术）
- 既有手术又有操作时，手术优先

## 4. 编码一致性 (consistency)
- 编码与患者性别是否一致（如妇科诊断/手术不应出现在男性患者）
- 编码与患者年龄是否一致（如围产期编码P码不应出现在成人）
- 主手术与主诊断在解剖部位/系统上应对应

## 5. 另编码/附加编码 (additional)
以下手术操作必须附加相应编码：
- 冠状动脉支架植入术(36.06/36.07) → 必须附加 00.66(支架数目) 和 00.40(血管内操作数目)
- 全髋关节置换术(81.51) → 必须附加 00.70(假体类型) 和 00.73(假体轴承面类型)
- 全膝关节置换术(81.54) → 必须附加 00.80(膝关节假体类型)
- 椎体融合术(81.0x) → 必须附加 81.62-81.64(融合节段数) 和 84.51(脊柱内固定装置植入)
- 经皮血管成形术 → 必须附加 00.40(血管内操作数目)

以下诊断必须附加相应编码：
- 损伤/中毒(S00-T98) → 必须附加外部原因编码(V01-Y98)
- 肿瘤**作为主诊断**(C00-C97) → 必须附加病理形态学编码(M码，如 M8140/3)
  M码仅主诊断为肿瘤时必需；次诊断、既往史中提及的肿瘤不需要M码

请严格按以下 JSON 格式输出，不要输出任何其他内容：
{
  "issues": [
    {
      "dimension": "merge|exclusion|primary|consistency|additional",
      "severity": "error|warning|info",
      "code": "涉及的编码",
      "description": "问题描述（含编码规则依据）",
      "suggestion": "具体的修改建议（含推荐编码）"
    }
  ],
  "summary": {
    "total_issues": 0,
    "overall_assessment": "通过|需修改|严重问题"
  }
}

重要原则：
- 只审查已编码的内容，不要基于临床推测或常识假设来报告未编码的问题
- 只报告确实存在的问题，不要过度报告
- 非肿瘤疾病不需要M码；肿瘤仅在**主诊断**时才需要M码，次诊断/既往史不需要
- severity 分级：error=编码规则明确禁止, warning=建议修改, info=可优化"""


# ===== 50条测试用例 =====
TEST_CASES = [
    # ===================== 1. 编码合并 (merge) × 10 =====================
    {
        "id": "M01", "category": "merge",
        "name": "糖尿病+肾病分编",
        "expected_dimension": "merge",
        "expected_codes": ["E11.9", "N08.3"],
        "prompt": """【患者信息】女，62岁
【诊断编码】
  主诊断：E11.900 2型糖尿病
  次诊断1：N08.300 糖尿病性肾病"""
    },
    {
        "id": "M02", "category": "merge",
        "name": "高血压+心脏病分编",
        "expected_dimension": "merge",
        "expected_codes": ["I10", "I51"],
        "prompt": """【患者信息】男，70岁
【诊断编码】
  主诊断：I10.x00 原发性高血压
  次诊断1：I51.900 心脏病（未特指）"""
    },
    {
        "id": "M03", "category": "merge",
        "name": "阑尾炎+腹膜炎分编",
        "expected_dimension": "merge",
        "expected_codes": ["K35.9", "K65.0"],
        "prompt": """【患者信息】男，45岁
【诊断编码】
  主诊断：K35.900 急性阑尾炎
  次诊断1：K65.000 急性腹膜炎
【手术操作编码】
  主手术：47.0901 阑尾切除术"""
    },
    {
        "id": "M04", "category": "merge",
        "name": "糖尿病+视网膜病变分编",
        "expected_dimension": "merge",
        "expected_codes": ["E11.9", "H36.0"],
        "prompt": """【患者信息】女，55岁
【诊断编码】
  主诊断：E11.900 2型糖尿病
  次诊断1：H36.000 糖尿病性视网膜病变"""
    },
    {
        "id": "M05", "category": "merge",
        "name": "结核+胸膜炎分编",
        "expected_dimension": "merge",
        "expected_codes": ["A15", "J90"],
        "prompt": """【患者信息】男，35岁
【诊断编码】
  主诊断：A15.000 肺结核
  次诊断1：J90.x00 结核性胸膜炎"""
    },
    {
        "id": "M06", "category": "merge",
        "name": "糖尿病+周围神经病分编",
        "expected_dimension": "merge",
        "expected_codes": ["E11.9", "G63.2"],
        "prompt": """【患者信息】女，68岁
【诊断编码】
  主诊断：E11.900 2型糖尿病
  次诊断1：G63.200 糖尿病性多发性神经病"""
    },
    {
        "id": "M07", "category": "merge",
        "name": "甲亢+甲状腺毒症性心脏病分编",
        "expected_dimension": "merge",
        "expected_codes": ["E05", "I43"],
        "prompt": """【患者信息】女，40岁
【诊断编码】
  主诊断：E05.900 甲状腺功能亢进症
  次诊断1：I43.800 甲状腺毒症性心脏病"""
    },
    {
        "id": "M08", "category": "merge",
        "name": "肺炎链球菌+肺炎分编",
        "expected_dimension": "merge",
        "expected_codes": ["B95.3", "J18"],
        "prompt": """【患者信息】男，72岁
【诊断编码】
  主诊断：J18.900 肺炎（未特指）
  次诊断1：B95.300 肺炎链球菌感染"""
    },
    {
        "id": "M09", "category": "merge",
        "name": "SLE+狼疮性肾炎分编",
        "expected_dimension": "merge",
        "expected_codes": ["M32", "N08"],
        "prompt": """【患者信息】女，28岁
【诊断编码】
  主诊断：M32.900 系统性红斑狼疮
  次诊断1：N08.500 狼疮性肾炎"""
    },
    {
        "id": "M10", "category": "merge",
        "name": "正确编码-不应报merge（无误病例）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】男，50岁
【诊断编码】
  主诊断：I25.103 冠状动脉粥样硬化性心脏病
  次诊断1：E78.500 高脂血症"""
    },

    # ===================== 2. 编码互斥 (exclusion) × 10 =====================
    {
        "id": "E01", "category": "exclusion",
        "name": "1型+2型糖尿病共存",
        "expected_dimension": "exclusion",
        "expected_codes": ["E10", "E11"],
        "prompt": """【患者信息】女，45岁
【诊断编码】
  主诊断：E10.900 1型糖尿病
  次诊断1：E11.900 2型糖尿病"""
    },
    {
        "id": "E02", "category": "exclusion",
        "name": "急性心梗+慢性缺血性心脏病",
        "expected_dimension": "exclusion",
        "expected_codes": ["I21", "I25"],
        "prompt": """【患者信息】男，65岁
【诊断编码】
  主诊断：I21.900 急性心肌梗死
  次诊断1：I25.900 慢性缺血性心脏病"""
    },
    {
        "id": "E03", "category": "exclusion",
        "name": "原发性+继发性高血压",
        "expected_dimension": "exclusion",
        "expected_codes": ["I10", "I15"],
        "prompt": """【患者信息】男，55岁
【诊断编码】
  主诊断：I10.x00 原发性高血压
  次诊断1：I15.900 继发性高血压"""
    },
    {
        "id": "E04", "category": "exclusion",
        "name": "同部位良性+恶性肿瘤",
        "expected_dimension": "exclusion",
        "expected_codes": ["C34", "D14"],
        "prompt": """【患者信息】男，60岁
【诊断编码】
  主诊断：C34.100 右肺上叶恶性肿瘤
  次诊断1：D14.300 右肺良性肿瘤"""
    },
    {
        "id": "E05", "category": "exclusion",
        "name": "急性+慢性胰腺炎",
        "expected_dimension": "exclusion",
        "expected_codes": ["K85", "K86"],
        "prompt": """【患者信息】男，48岁
【诊断编码】
  主诊断：K85.900 急性胰腺炎
  次诊断1：K86.100 慢性胰腺炎"""
    },
    {
        "id": "E06", "category": "exclusion",
        "name": "急性+慢性肾功能衰竭",
        "expected_dimension": "exclusion",
        "expected_codes": ["N17", "N18"],
        "prompt": """【患者信息】女，70岁
【诊断编码】
  主诊断：N17.900 急性肾功能衰竭
  次诊断1：N18.900 慢性肾功能衰竭"""
    },
    {
        "id": "E07", "category": "exclusion",
        "name": "甲亢+甲减",
        "expected_dimension": "exclusion",
        "expected_codes": ["E05", "E03"],
        "prompt": """【患者信息】女，38岁
【诊断编码】
  主诊断：E05.900 甲状腺功能亢进症
  次诊断1：E03.900 甲状腺功能减退症"""
    },
    {
        "id": "E08", "category": "exclusion",
        "name": "上下级重复-肺炎+肺炎链球菌性肺炎",
        "expected_dimension": "exclusion",
        "expected_codes": ["J18", "J13"],
        "prompt": """【患者信息】男，60岁
【诊断编码】
  主诊断：J13.x00 肺炎链球菌性肺炎
  次诊断1：J18.900 肺炎（未特指）"""
    },
    {
        "id": "E09", "category": "exclusion",
        "name": "前列腺增生+前列腺恶性肿瘤",
        "expected_dimension": "exclusion",
        "expected_codes": ["N40", "C61"],
        "prompt": """【患者信息】男，75岁
【诊断编码】
  主诊断：C61.x00 前列腺恶性肿瘤
  次诊断1：N40.x00 前列腺增生"""
    },
    {
        "id": "E10", "category": "exclusion",
        "name": "正确编码-不应报exclusion（无误病例）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】女，55岁
【诊断编码】
  主诊断：I10.x00 原发性高血压
  次诊断1：E11.900 2型糖尿病
  次诊断2：E78.500 高脂血症"""
    },

    # ===================== 3. 主诊断选择 (primary) × 10 =====================
    {
        "id": "P01", "category": "primary",
        "name": "R码做主诊-腹痛（有明确病因）",
        "expected_dimension": "primary",
        "expected_codes": ["R10"],
        "prompt": """【患者信息】男，30岁
【诊断编码】
  主诊断：R10.400 腹痛
  次诊断1：K35.900 急性阑尾炎
【手术操作编码】
  主手术：47.0901 阑尾切除术"""
    },
    {
        "id": "P02", "category": "primary",
        "name": "R码做主诊-发热（有肺炎）",
        "expected_dimension": "primary",
        "expected_codes": ["R50"],
        "prompt": """【患者信息】女，65岁
【诊断编码】
  主诊断：R50.900 发热（原因不明）
  次诊断1：J18.100 大叶性肺炎"""
    },
    {
        "id": "P03", "category": "primary",
        "name": "诊断码做主诊但不是手术对象",
        "expected_dimension": "primary",
        "expected_codes": ["I10"],
        "prompt": """【患者信息】男，58岁
【诊断编码】
  主诊断：I10.x00 原发性高血压
  次诊断1：K80.100 胆囊结石伴急性胆囊炎
【手术操作编码】
  主手术：51.2300 腹腔镜胆囊切除术"""
    },
    {
        "id": "P04", "category": "primary",
        "name": "Z码做主诊-非化疗/康复场景",
        "expected_dimension": "primary",
        "expected_codes": ["Z53"],
        "prompt": """【患者信息】女，40岁
【诊断编码】
  主诊断：Z53.900 未进行的手术操作
  次诊断1：K80.200 胆囊结石
  次诊断2：I10.x00 高血压"""
    },
    {
        "id": "P05", "category": "primary",
        "name": "诊断做主诊-造影术为主术（非治疗手段）",
        "expected_dimension": "primary",
        "expected_codes": ["88.55"],
        "prompt": """【患者信息】男，60岁
【诊断编码】
  主诊断：I25.103 冠状动脉粥样硬化性心脏病
【手术操作编码】
  主手术：88.5500 经皮冠状动脉造影术
  其他手术1：36.0601 经皮冠状动脉药物洗脱支架植入术"""
    },
    {
        "id": "P06", "category": "primary",
        "name": "R码做主诊-胸痛（有心梗）",
        "expected_dimension": "primary",
        "expected_codes": ["R07"],
        "prompt": """【患者信息】男，55岁
【诊断编码】
  主诊断：R07.400 胸痛
  次诊断1：I21.001 急性前壁心肌梗死"""
    },
    {
        "id": "P07", "category": "primary",
        "name": "R码做主诊-头痛（有脑出血）",
        "expected_dimension": "primary",
        "expected_codes": ["R51"],
        "prompt": """【患者信息】女，60岁
【诊断编码】
  主诊断：R51.x00 头痛
  次诊断1：I61.000 脑出血"""
    },
    {
        "id": "P08", "category": "primary",
        "name": "正确Z码做主诊-化疗（应通过）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】女，50岁
【诊断编码】
  主诊断：Z51.100 肿瘤化学治疗疗程
  次诊断1：C50.900 乳腺恶性肿瘤"""
    },
    {
        "id": "P09", "category": "primary",
        "name": "R码做主诊-呕吐（有肠梗阻）",
        "expected_dimension": "primary",
        "expected_codes": ["R11"],
        "prompt": """【患者信息】男，72岁
【诊断编码】
  主诊断：R11.x00 恶心和呕吐
  次诊断1：K56.600 肠梗阻"""
    },
    {
        "id": "P10", "category": "primary",
        "name": "正确主诊断（应通过）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】男，45岁
【诊断编码】
  主诊断：K35.900 急性阑尾炎
  次诊断1：I10.x00 高血压
【手术操作编码】
  主手术：47.0901 阑尾切除术"""
    },

    # ===================== 4. 编码一致性 (consistency) × 10 =====================
    {
        "id": "C01", "category": "consistency",
        "name": "男性-妇科诊断（子宫肌瘤）",
        "expected_dimension": "consistency",
        "expected_codes": ["D25"],
        "prompt": """【患者信息】男，55岁
【诊断编码】
  主诊断：D25.900 子宫平滑肌瘤"""
    },
    {
        "id": "C02", "category": "consistency",
        "name": "男性-妊娠诊断",
        "expected_dimension": "consistency",
        "expected_codes": ["O"],
        "prompt": """【患者信息】男，30岁
【诊断编码】
  主诊断：O80.000 正常分娩"""
    },
    {
        "id": "C03", "category": "consistency",
        "name": "女性-前列腺诊断",
        "expected_dimension": "consistency",
        "expected_codes": ["N40"],
        "prompt": """【患者信息】女，70岁
【诊断编码】
  主诊断：N40.x00 前列腺增生"""
    },
    {
        "id": "C04", "category": "consistency",
        "name": "成人-新生儿编码P码",
        "expected_dimension": "consistency",
        "expected_codes": ["P"],
        "prompt": """【患者信息】男，45岁
【诊断编码】
  主诊断：P07.100 低出生体重儿"""
    },
    {
        "id": "C05", "category": "consistency",
        "name": "男性-卵巢手术",
        "expected_dimension": "consistency",
        "expected_codes": ["65"],
        "prompt": """【患者信息】男，40岁
【诊断编码】
  主诊断：D27.x00 卵巢良性肿瘤
【手术操作编码】
  主手术：65.2900 卵巢切除术"""
    },
    {
        "id": "C06", "category": "consistency",
        "name": "主手术与主诊断不匹配-骨科诊断+腹部手术",
        "expected_dimension": "consistency",
        "expected_codes": ["M17", "47"],
        "prompt": """【患者信息】男，60岁
【诊断编码】
  主诊断：M17.100 膝关节骨性关节炎
【手术操作编码】
  主手术：47.0901 阑尾切除术"""
    },
    {
        "id": "C07", "category": "consistency",
        "name": "女性-睾丸疾病",
        "expected_dimension": "consistency",
        "expected_codes": ["N44"],
        "prompt": """【患者信息】女，25岁
【诊断编码】
  主诊断：N44.x00 睾丸扭转"""
    },
    {
        "id": "C08", "category": "consistency",
        "name": "儿童-老年性白内障",
        "expected_dimension": "consistency",
        "expected_codes": ["H25"],
        "prompt": """【患者信息】男，5岁
【诊断编码】
  主诊断：H25.900 老年性白内障"""
    },
    {
        "id": "C09", "category": "consistency",
        "name": "男性-子宫切除手术",
        "expected_dimension": "consistency",
        "expected_codes": ["68"],
        "prompt": """【患者信息】男，50岁
【诊断编码】
  主诊断：D25.100 子宫壁内平滑肌瘤
【手术操作编码】
  主手术：68.4900 全子宫切除术"""
    },
    {
        "id": "C10", "category": "consistency",
        "name": "正确一致性（应通过）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】女，60岁
【诊断编码】
  主诊断：D25.100 子宫壁内平滑肌瘤
【手术操作编码】
  主手术：68.4900 全子宫切除术"""
    },

    # ===================== 5. 另编码/附加编码 (additional) × 10 =====================
    {
        "id": "A01", "category": "additional",
        "name": "冠脉支架缺00.66+00.40",
        "expected_dimension": "additional",
        "expected_codes": ["36.06", "00.66", "00.40"],
        "prompt": """【患者信息】男，58岁
【诊断编码】
  主诊断：I25.103 冠状动脉粥样硬化性心脏病
【手术操作编码】
  主手术：36.0601 经皮冠状动脉药物洗脱支架植入术
  其他手术1：88.5500 经皮冠状动脉造影术"""
    },
    {
        "id": "A02", "category": "additional",
        "name": "全髋置换缺00.70+00.73",
        "expected_dimension": "additional",
        "expected_codes": ["81.51", "00.70", "00.73"],
        "prompt": """【患者信息】女，72岁
【诊断编码】
  主诊断：M16.100 髋关节骨性关节炎
【手术操作编码】
  主手术：81.5100 全髋关节置换术"""
    },
    {
        "id": "A03", "category": "additional",
        "name": "全膝置换缺00.80",
        "expected_dimension": "additional",
        "expected_codes": ["81.54", "00.80"],
        "prompt": """【患者信息】男，68岁
【诊断编码】
  主诊断：M17.100 膝关节骨性关节炎
【手术操作编码】
  主手术：81.5400 全膝关节置换术"""
    },
    {
        "id": "A04", "category": "additional",
        "name": "椎体融合缺节段数+内固定",
        "expected_dimension": "additional",
        "expected_codes": ["81.0", "81.6", "84.51"],
        "prompt": """【患者信息】男，55岁
【诊断编码】
  主诊断：M51.100 腰椎间盘突出症
【手术操作编码】
  主手术：81.0600 腰椎椎体融合术"""
    },
    {
        "id": "A05", "category": "additional",
        "name": "肿瘤主诊断缺M码",
        "expected_dimension": "additional",
        "expected_codes": ["C34", "M"],
        "prompt": """【患者信息】男，62岁
【诊断编码】
  主诊断：C34.100 右肺上叶恶性肿瘤
【手术操作编码】
  主手术：32.4100 肺叶切除术"""
    },
    {
        "id": "A06", "category": "additional",
        "name": "损伤缺外因码V-Y",
        "expected_dimension": "additional",
        "expected_codes": ["S72", "V", "W", "Y"],
        "prompt": """【患者信息】男，35岁
【诊断编码】
  主诊断：S72.000 股骨颈骨折
【手术操作编码】
  主手术：79.3501 股骨内固定术"""
    },
    {
        "id": "A07", "category": "additional",
        "name": "中毒缺外因码",
        "expected_dimension": "additional",
        "expected_codes": ["T39", "Y"],
        "prompt": """【患者信息】女，22岁
【诊断编码】
  主诊断：T39.100 对乙酰氨基酚中毒"""
    },
    {
        "id": "A08", "category": "additional",
        "name": "冠脉支架已有附加码（应通过）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】男，58岁
【诊断编码】
  主诊断：I25.103 冠状动脉粥样硬化性心脏病
【手术操作编码】
  主手术：36.0601 经皮冠状动脉药物洗脱支架植入术
  其他手术1：88.5500 经皮冠状动脉造影术
  其他手术2：00.6601 植入1个支架
  其他手术3：00.4001 1根血管内操作"""
    },
    {
        "id": "A09", "category": "additional",
        "name": "肿瘤非主诊断（不需M码，应通过）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】女，50岁
【诊断编码】
  主诊断：J18.100 大叶性肺炎
  次诊断1：C50.900 乳腺恶性肿瘤（既往史）"""
    },
    {
        "id": "A10", "category": "additional",
        "name": "全髋已有附加码（应通过）",
        "expected_dimension": "none",
        "expected_codes": [],
        "prompt": """【患者信息】女，72岁
【诊断编码】
  主诊断：M16.100 髋关节骨性关节炎
【手术操作编码】
  主手术：81.5100 全髋关节置换术
  其他手术1：00.7001 金属对聚乙烯假体
  其他手术2：00.7300 陶瓷对聚乙烯轴承面"""
    },
]


async def call_llm(client: httpx.AsyncClient, case: dict) -> dict:
    """调用 LLM 并返回结果"""
    user_prompt = f"请对以下病案首页编码进行质控审查：\n\n{case['prompt']}"
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "enable_thinking": False,
    }

    t0 = time.time()
    try:
        r = await client.post(
            f"{API_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=body,
            timeout=60,
        )
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        elapsed = time.time() - t0

        # 解析 JSON
        try:
            result = json.loads(content)
        except:
            # 尝试提取 JSON
            import re
            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                result = json.loads(m.group())
            else:
                result = {"issues": [], "summary": {"total_issues": 0, "overall_assessment": "解析失败"}}

        return {
            "case_id": case["id"],
            "case_name": case["name"],
            "category": case["category"],
            "expected_dimension": case["expected_dimension"],
            "elapsed": round(elapsed, 2),
            "issues": result.get("issues", []),
            "assessment": result.get("summary", {}).get("overall_assessment", ""),
            "raw": content,
        }
    except Exception as e:
        return {
            "case_id": case["id"],
            "case_name": case["name"],
            "category": case["category"],
            "expected_dimension": case["expected_dimension"],
            "elapsed": time.time() - t0,
            "issues": [],
            "assessment": f"ERROR: {e}",
            "raw": str(e),
        }


def evaluate(result: dict) -> str:
    """评分：PASS / FAIL / FALSE_POSITIVE"""
    expected = result["expected_dimension"]
    issues = result["issues"]
    found_dims = [i.get("dimension") for i in issues]

    if expected == "none":
        # 无误病例：不应报出该类别问题
        cat = result["category"]
        if cat in found_dims:
            return "FALSE_POSITIVE"  # 误报
        return "PASS"
    else:
        # 有问题病例：应该检出
        if expected in found_dims:
            return "PASS"
        return "FAIL"  # 漏报


async def main():
    print(f"模型: {MODEL}")
    print(f"测试用例: {len(TEST_CASES)} 条 (5维度 × 10条)")
    print("=" * 70)

    # 并发5个一组
    semaphore = asyncio.Semaphore(5)
    results = []

    async with httpx.AsyncClient() as client:
        async def bounded_call(case):
            async with semaphore:
                return await call_llm(client, case)

        tasks = [bounded_call(c) for c in TEST_CASES]
        results = await asyncio.gather(*tasks)

    # 评分
    categories = ["merge", "exclusion", "primary", "consistency", "additional"]
    cat_results = {c: {"pass": 0, "fail": 0, "fp": 0, "total": 0} for c in categories}

    lines = []
    for r in results:
        grade = evaluate(r)
        cat = r["category"]
        cat_results[cat]["total"] += 1
        if grade == "PASS":
            cat_results[cat]["pass"] += 1
        elif grade == "FAIL":
            cat_results[cat]["fail"] += 1
        else:
            cat_results[cat]["fp"] += 1

        icon = "✅" if grade == "PASS" else ("❌" if grade == "FAIL" else "⚠️")
        found_dims = [i.get("dimension") for i in r["issues"]]
        lines.append(f"{icon} {r['case_id']} {r['case_name']:<25s} | 期望:{r['expected_dimension']:<12s} | 检出:{','.join(found_dims) or '无':<20s} | {r['elapsed']:.1f}s | {grade}")

    # 汇总报告
    report = []
    report.append(f"编码质控 LLM Prompt 基准测试报告")
    report.append(f"模型: {MODEL}")
    report.append(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)
    report.append("")

    report.append("## 各维度得分")
    report.append(f"{'维度':<15s} {'通过':>5s} {'漏报':>5s} {'误报':>5s} {'总数':>5s} {'准确率':>8s}")
    report.append("-" * 55)
    total_pass = total_fail = total_fp = 0
    for cat in categories:
        cr = cat_results[cat]
        rate = f"{cr['pass']/cr['total']*100:.0f}%" if cr['total'] else "N/A"
        report.append(f"{cat:<15s} {cr['pass']:>5d} {cr['fail']:>5d} {cr['fp']:>5d} {cr['total']:>5d} {rate:>8s}")
        total_pass += cr['pass']
        total_fail += cr['fail']
        total_fp += cr['fp']

    total = len(results)
    report.append("-" * 55)
    report.append(f"{'总计':<15s} {total_pass:>5d} {total_fail:>5d} {total_fp:>5d} {total:>5d} {total_pass/total*100:.0f}%")
    report.append("")

    report.append("## 详细结果")
    current_cat = ""
    for line in lines:
        case_cat = line.split()[1][0]  # M/E/P/C/A
        cat_map = {"M": "merge", "E": "exclusion", "P": "primary", "C": "consistency", "A": "additional"}
        cat_name = cat_map.get(case_cat, "")
        if cat_name != current_cat:
            report.append(f"\n### {cat_name}")
            current_cat = cat_name
        report.append(line)

    # 失败用例详情
    failures = [r for r in results if evaluate(r) != "PASS"]
    if failures:
        report.append(f"\n## 失败/误报用例详情 ({len(failures)}条)")
        for r in failures:
            grade = evaluate(r)
            report.append(f"\n--- {r['case_id']} {r['case_name']} ({grade}) ---")
            report.append(f"期望维度: {r['expected_dimension']}")
            for i, iss in enumerate(r["issues"]):
                report.append(f"  Issue {i+1}: [{iss.get('dimension')}] {iss.get('description', '')[:100]}")
            if not r["issues"]:
                report.append("  (未检出任何问题)")

    full_report = "\n".join(report)

    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(full_report)

    print(full_report)


if __name__ == "__main__":
    asyncio.run(main())
