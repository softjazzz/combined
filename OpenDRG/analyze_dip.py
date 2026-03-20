"""分析 OpenDIP 国家版的结构和分组逻辑"""
import re, sys
sys.stdout.reconfigure(encoding='utf-8')

idx_path = r'D:\大模型项目\lx0222\health-qc-monorepo\OpenDRG\OpenDIP\national\index.js'
with open(idx_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f'=== index.js 基本信息 ===')
print(f'文件大小: {len(content)} 字符')

# 搜索关键函数名
for keyword in ['group_record', 'getDipCode', 'dip_group', 'groupDip', 'matchDip', 'classify']:
    count = content.count(keyword)
    if count > 0:
        print(f'  函数 "{keyword}" 出现 {count} 次')

# 搜索方案名
print(f'\n=== 方案名 ===')
for m in re.finditer(r'"(national|國家|国家|sichuan|四川|海南|辽宁|大庆|秦皇岛|云浮|贵阳|郑州|洛阳|南阳|阿克苏)', content):
    start = max(0, m.start()-20)
    end = min(len(content), m.end()+80)
    print(content[start:end][:120])
    print()

# 搜索关键数据结构
print(f'\n=== 数据结构关键词 ===')
for keyword in ['诊断', '手术', '操作', 'ICD', '分值', '病种', 'DIP', '目录', '核心', '综合']:
    count = content.count(keyword)
    if count > 0:
        print(f'  "{keyword}" 出现 {count} 次')

# group_record 上下文
print(f'\n=== group_record 上下文 ===')
for m in re.finditer(r'group_record', content):
    start = max(0, m.start()-100)
    end = min(len(content), m.end()+200)
    print(content[start:end])
    print('---')

# chunk 映射
print(f'\n=== Chunk 动态导入映射 ===')
for m in re.finditer(r'\./(\w+)\.js.*?:\[(\d+(?:,\d+)*)\]', content):
    print(f'  {m.group(1)}.js -> chunk [{m.group(2)}]')
