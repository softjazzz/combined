"""直接调 DashScope API 测试 LLM 切分"""
import json, os, requests
from dotenv import load_dotenv
from _import_and_test_qc import CASE_1_ZHANGSAN

# 从 .env 读配置
load_dotenv('backend/.env')
API_ENDPOINT = os.getenv('LLM_API_ENDPOINT')
API_KEY = os.getenv('LLM_API_KEY')
MODEL = os.getenv('LLM_MODEL', 'qwen-turbo')

print(f"Endpoint: {API_ENDPOINT}")
print(f"Model: {MODEL}")
print(f"Content: {len(CASE_1_ZHANGSAN)} chars")

# 构建带行号文本
lines = CASE_1_ZHANGSAN.split('\n')
numbered = '\n'.join(f'{i+1}: {line}' for i, line in enumerate(lines))

SPLIT_PROMPT = """你是一个医疗病历文档分段专家。请分析以下完整住院病历文本，识别其中包含的所有独立医疗文书段落。

要求：
1. 识别每个文书段落的标题、类型、起始行号和结束行号
2. 行号从 1 开始计数
3. 文书类型必须是以下标准类型之一：
   - admission_record（入院记录）
   - first_course_record（首次病程记录）
   - daily_course_record（日常病程记录、术后病程记录、普通病程记录）
   - senior_course_record（主任/副主任查房记录、上级医师查房记录）
   - surgery_record（手术记录）
   - presurg_discussion（术前讨论记录）
   - presurg_summary（术前小结）
   - postsurg_firstcourse_record（术后首次病程记录）
   - discharge_record（出院记录、出院小结）
   - death_record（死亡记录）
   - death_discussion（死亡讨论）
   - consultation_record（会诊记录）
   - rescue_record（抢救记录）
   - consent_form（知情同意书、谈话记录）
   - anesthesia_record（麻醉记录）
   - summary_record（阶段小结）
   - diffcase_discussion_record（疑难病例讨论）
4. 跳过非正式文书段落（如费用清单、病案首页基本信息等）
5. 分隔线（如 ====）不属于任何段落内容

请以JSON数组格式返回，每个元素：
{"title": "段落标题", "type": "标准文书类型", "start_line": 起始行号, "end_line": 结束行号}

只返回JSON数组，不要额外文字。"""

prompt = f"""{SPLIT_PROMPT}

以下是带行号的完整住院病历文本（共 {len(lines)} 行）：

{numbered}"""

print(f"\nPrompt length: {len(prompt)} chars")
print("Calling LLM...")

resp = requests.post(
    f"{API_ENDPOINT}/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
        "enable_thinking": False,
    },
    timeout=60,
)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    content = data['choices'][0]['message']['content']
    usage = data.get('usage', {})
    print(f"Tokens: {usage.get('total_tokens', '?')}")
    print(f"\nLLM Response:\n{content}")
    
    # Parse JSON
    try:
        sections = json.loads(content)
        print(f"\n=== Parsed: {len(sections)} sections ===")
        for i, s in enumerate(sections, 1):
            print(f"  {i}. [{s['type']}] {s['title']} (lines {s['start_line']}-{s['end_line']})")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
else:
    print(f"Error: {resp.text[:500]}")
