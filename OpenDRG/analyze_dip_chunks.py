"""深入分析 OpenDIP chunk 文件和分组逻辑"""
import os, sys, re, json
sys.stdout.reconfigure(encoding='utf-8')

base = r'D:\大模型项目\lx0222\health-qc-monorepo\OpenDRG\OpenDIP\national'

# 列出所有 JS chunk 及大小
print('=== Chunk 文件 ===')
files = []
for f in os.listdir(base):
    if f.endswith('.js') and f not in ('index.js', 'runtime.js'):
        size = os.path.getsize(os.path.join(base, f))
        files.append((f, size))
        print(f'  {f}: {size/1024:.0f} KB')
files.sort(key=lambda x: -x[1])

# 分析最大的几个 chunk
for fname, size in files[:5]:
    path = os.path.join(base, fname)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f'\n=== {fname} ({size/1024:.0f} KB) ===')
    
    # 是否混淆
    hex_vars = len(re.findall(r'_0x[a-f0-9]+', content))
    print(f'  混淆变量数: {hex_vars}')
    
    # 关键词搜索
    for kw in ['group_record', 'dip_group', 'SS_INVALID', 'ICD', 'zhenduan', 'shoushu', 
                '诊断', '手术', '操作', '病种', '核心', '综合', '分值', 'DIP', 'MDC']:
        count = content.count(kw)
        if count > 0:
            print(f'  "{kw}" 出现 {count} 次')
    
    # 查看开头结构
    head = content[:500].replace('\n', ' ')
    print(f'  开头: {head[:200]}...')

# 分析 index.js 中的动态模块映射
print('\n=== index.js 模块映射 ===')
with open(os.path.join(base, 'index.js'), 'r', encoding='utf-8') as f:
    idx = f.read()

# 找 chunk id 到模块名的映射
for m in re.finditer(r'"\./([\w_]+)\.js"\s*:\s*\[([^\]]+)\]', idx):
    print(f'  {m.group(1)}.js -> [{m.group(2)}]')

# 找方案列表
for m in re.finditer(r'(national|guojia|sichuan|hainan|liaoning|daqing|qinhuangdao|yunfu|guiyang|zhengzhou|luoyang|nanyang|akesu)', idx, re.IGNORECASE):
    start = max(0, m.start()-30)
    end = min(len(idx), m.end()+100)
    snippet = idx[start:end]
    if 'national' in snippet.lower() or 'guojia' in snippet.lower():
        print(f'  方案映射: {snippet[:150]}')
        break

# Excel 文件
print('\n=== 数据文件(Excel) ===')
for f in os.listdir(base):
    if f.endswith('.xlsx'):
        size = os.path.getsize(os.path.join(base, f))
        print(f'  {f}: {size/1024:.0f} KB')
