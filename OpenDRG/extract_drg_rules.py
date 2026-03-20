"""
OpenDRG 全量 DRG 分组方案批量提取器
从 opendrg.github.io 编译的 webpack chunk 文件中提取 39 个方案的分组规则数据
"""
import json
import re
import os
import time
from pathlib import Path
from datetime import datetime

# ============================================================
# 方案分类映射表
# ============================================================
SCHEME_CATALOG = {
    # --- 国家版标准 ---
    "chs_drg_11":    {"category": "national", "path": "national/chs_drg_11",    "label": "CHS-DRG 1.1"},
    "chs_drg_11p":   {"category": "national", "path": "national/chs_drg_11p",   "label": "CHS-DRG 1.1 改进版"},
    "chs_drg_20":    {"category": "national", "path": "national/chs_drg_20",    "label": "CHS-DRG 2.0"},
    "cn_drg_2023":   {"category": "national", "path": "national/cn_drg_2023",   "label": "CN-DRG 2023"},

    # --- 直辖市 ---
    "beijing_2024":   {"category": "municipality", "path": "municipality/beijing_2024",   "label": "北京 2024"},
    "chongqing_2024": {"category": "municipality", "path": "municipality/chongqing_2024", "label": "重庆 2024"},
    "shanghai_2023":  {"category": "municipality", "path": "municipality/shanghai_2023",  "label": "上海 2023"},
    "tianjin_2025":   {"category": "municipality", "path": "municipality/tianjin_2025",   "label": "天津 2025"},

    # --- 省级方案 ---
    "fujian_2024":   {"category": "province", "path": "province/fujian_2024",   "label": "福建 2024"},
    "hubei_2024":    {"category": "province", "path": "province/hubei_2024",    "label": "湖北 2024"},
    "qinghai_2024":  {"category": "province", "path": "province/qinghai_2024",  "label": "青海 2024"},
    "sichuan_2024":  {"category": "province", "path": "province/sichuan_2024",  "label": "四川 2024"},
    "xinjiang_2025": {"category": "province", "path": "province/xinjiang_2025", "label": "新疆 2025"},

    # --- 地市级方案 ---
    # 安徽省
    "bengbu_2023":    {"category": "city", "path": "city/anhui/bengbu_2023",    "label": "蚌埠 2023", "province": "安徽"},
    "huaibei_2025":   {"category": "city", "path": "city/anhui/huaibei_2025",   "label": "淮北 2025", "province": "安徽"},
    "maanshan_2023":  {"category": "city", "path": "city/anhui/maanshan_2023",  "label": "马鞍山 2023", "province": "安徽"},
    "tongling_2024":  {"category": "city", "path": "city/anhui/tongling_2024",  "label": "铜陵 2024", "province": "安徽"},
    # 广东省
    "foshan_2025":    {"category": "city", "path": "city/guangdong/foshan_2025", "label": "佛山 2025", "province": "广东"},
    # 河北省
    "dingzhou_2023":  {"category": "city", "path": "city/hebei/dingzhou_2023",  "label": "定州 2023", "province": "河北"},
    "handan_2025":    {"category": "city", "path": "city/hebei/handan_2025",    "label": "邯郸 2025", "province": "河北"},
    # 河南省
    "jiyuan_2023":    {"category": "city", "path": "city/henan/jiyuan_2023",    "label": "济源 2023", "province": "河南"},
    "kaifeng_2024":   {"category": "city", "path": "city/henan/kaifeng_2024",   "label": "开封 2024", "province": "河南"},
    "luohe_2023":     {"category": "city", "path": "city/henan/luohe_2023",     "label": "漯河 2023", "province": "河南"},
    # 湖南省
    "changsha_2024":  {"category": "city", "path": "city/hunan/changsha_2024",  "label": "长沙 2024", "province": "湖南"},
    "chenzhou_2025":  {"category": "city", "path": "city/hunan/chenzhou_2025",  "label": "郴州 2025", "province": "湖南"},
    # 江苏省
    "nanjing_2024":   {"category": "city", "path": "city/jiangsu/nanjing_2024", "label": "南京 2024", "province": "江苏"},
    "wuxi_2023":      {"category": "city", "path": "city/jiangsu/wuxi_2023",    "label": "无锡 2023", "province": "江苏"},
    "yancheng_2023":  {"category": "city", "path": "city/jiangsu/yancheng_2023","label": "盐城 2023", "province": "江苏"},
    # 江西省
    "nanchang_2025":  {"category": "city", "path": "city/jiangxi/nanchang_2025","label": "南昌 2025", "province": "江西"},
    "shangrao_2025":  {"category": "city", "path": "city/jiangxi/shangrao_2025","label": "上饶 2025", "province": "江西"},
    # 福建省(市级)
    "nanping_2023":   {"category": "city", "path": "city/fujian/nanping_2023",  "label": "南平 2023", "province": "福建"},
    # 宁夏
    "yinchuan_2023":  {"category": "city", "path": "city/ningxia/yinchuan_2023","label": "银川 2023", "province": "宁夏"},
    # 陕西省
    "ankang_2025":    {"category": "city", "path": "city/shaanxi/ankang_2025",  "label": "安康 2025", "province": "陕西"},
    "xianyang_2025":  {"category": "city", "path": "city/shaanxi/xianyang_2025","label": "咸阳 2025", "province": "陕西"},
    # 山东省
    "liaocheng_2025": {"category": "city", "path": "city/shandong/liaocheng_2025","label": "聊城 2025", "province": "山东"},
    "yantai_2024":    {"category": "city", "path": "city/shandong/yantai_2024",  "label": "烟台 2024", "province": "山东"},
    "zaozhuang_2025": {"category": "city", "path": "city/shandong/zaozhuang_2025","label": "枣庄 2025", "province": "山东"},
    # 山西省
    "datong_2023":    {"category": "city", "path": "city/shanxi/datong_2023",   "label": "大同 2023", "province": "山西"},
    "linfen_2022":    {"category": "city", "path": "city/shanxi/linfen_2022",   "label": "临汾 2022", "province": "山西"},
}

# ============================================================
# 核心提取函数
# ============================================================

BASE_DIR = Path(__file__).parent
JS_DIR = BASE_DIR / "opendrg.github.io"
OUTPUT_BASE = BASE_DIR / "extracted_rules"


def get_chunk_mapping():
    """从 index.js 中读取方案名 -> chunk ID 映射"""
    with open(JS_DIR / "index.js", 'r', encoding='utf-8') as f:
        content = f.read()
    mappings = re.findall(r'"\./([\w_]+)\.js":\s*\[(\d+)', content)
    return {name: chunk_id for name, chunk_id in mappings}


def extract_json_parse_data(content, var_name):
    """提取 var_name=JSON.parse('...') 中的 JSON 数据"""
    pattern = rf'{var_name}=JSON\.parse\(\''
    match = re.search(pattern, content)
    if not match:
        return None
    start = match.end()
    i = start
    while i < len(content):
        if content[i] == '\\' and i + 1 < len(content):
            i += 2
            continue
        if content[i] == "'":
            json_str = content[start:i]
            break
        i += 1
    else:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def find_export_var_names(content):
    """找到导出名与变量名的映射，兼容不同 chunk 的变量命名"""
    exports = re.findall(r'(\w+):\(\)=>(\w+)', content)
    mapping = {}
    for export_name, var_name in exports:
        if export_name in ('CC', 'CCE', 'MCC', 'SS_VALID', 'group_record', 'group_record_str'):
            mapping[export_name] = var_name
    return mapping


def extract_drg_group_info(content):
    """提取 DRG 分组函数信息"""
    groups = {}
    pattern = r'(\w{2}\d{2})_group\(x\)\{return\s*(.+?)\}'
    for match in re.finditer(pattern, content):
        func_name = match.group(1)
        body = match.group(2)
        adrg = func_name[:2]
        if adrg not in groups:
            groups[adrg] = {}
        if body == '!0':
            condition = '无条件入组'
        elif 'mccList.length>0' in body and 'ccList' not in body:
            condition = '需要MCC'
        elif 'mccList.length>0||x.ccList.length>0' in body:
            condition = '需要CC或MCC'
        else:
            condition = body[:60]
        groups[adrg][func_name] = {"suffix": func_name[2:], "condition": condition}
    return groups


def extract_single_scheme(scheme_name, chunk_id, output_dir):
    """提取单个方案的全部数据"""
    js_file = JS_DIR / f"{chunk_id}.js"
    if not js_file.exists():
        return {"status": "error", "message": f"chunk 文件不存在: {js_file}"}

    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 找到导出变量名映射
    var_map = find_export_var_names(content)
    os.makedirs(output_dir, exist_ok=True)

    stats = {}

    # 提取 CCE
    if 'CCE' in var_map:
        data = extract_json_parse_data(content, var_map['CCE'])
        if data:
            with open(output_dir / "cce_icd_to_mdc.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            stats['cce'] = len(data)

    # 提取 MCC
    if 'MCC' in var_map:
        data = extract_json_parse_data(content, var_map['MCC'])
        if data:
            with open(output_dir / "mcc_major_complications.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            stats['mcc'] = len(data)

    # 提取 CC
    if 'CC' in var_map:
        data = extract_json_parse_data(content, var_map['CC'])
        if data:
            with open(output_dir / "cc_complications.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            stats['cc'] = len(data)

    # 提取 SS_VALID
    if 'SS_VALID' in var_map:
        data = extract_json_parse_data(content, var_map['SS_VALID'])
        if data:
            with open(output_dir / "ss_valid_procedures.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            stats['ss_valid'] = len(data)

    # 提取 DRG 分组
    drg_groups = extract_drg_group_info(content)
    if drg_groups:
        with open(output_dir / "drg_groups.json", 'w', encoding='utf-8') as f:
            json.dump(drg_groups, f, ensure_ascii=False, indent=2)
        total_drgs = sum(len(v) for v in drg_groups.values())
        stats['adrg'] = len(drg_groups)
        stats['drg'] = total_drgs

    # 生成 metadata.json
    catalog_info = SCHEME_CATALOG.get(scheme_name, {})
    metadata = {
        "scheme_name": scheme_name,
        "label": catalog_info.get("label", scheme_name),
        "category": catalog_info.get("category", "unknown"),
        "province": catalog_info.get("province", ""),
        "source_file": f"{chunk_id}.js",
        "extracted_at": datetime.now().isoformat(),
        "stats": stats,
    }
    with open(output_dir / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "stats": stats}


def generate_readme(all_results):
    """生成 README.md 汇总"""
    lines = [
        "# OpenDRG 分组规则数据",
        "",
        f"> 提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 数据来源: opendrg.github.io 编译 JS",
        f"> 方案总数: {len(all_results)} 个",
        "",
        "## 目录结构",
        "",
        "```",
        "extracted_rules/",
        "├── national/        # 国家版标准 (4个)",
        "├── municipality/    # 直辖市 (4个)",
        "├── province/        # 省级方案 (5个)",
        "└── city/            # 地市级方案 (26个，按省份分组)",
        "```",
        "",
        "## 方案一览",
        "",
        "| 分类 | 方案 | 标签 | CCE | MCC | CC | SS_VALID | ADRG | DRG |",
        "|------|------|------|-----|-----|----|----------|------|-----|",
    ]

    category_labels = {
        "national": "国家版",
        "municipality": "直辖市",
        "province": "省级",
        "city": "地市级",
    }

    for name, result in sorted(all_results.items(), key=lambda x: SCHEME_CATALOG.get(x[0], {}).get("path", "")):
        info = SCHEME_CATALOG.get(name, {})
        cat = category_labels.get(info.get("category", ""), "")
        label = info.get("label", name)
        s = result.get("stats", {})
        lines.append(
            f"| {cat} | {name} | {label} | "
            f"{s.get('cce', '-'):,} | {s.get('mcc', '-'):,} | {s.get('cc', '-'):,} | "
            f"{s.get('ss_valid', '-'):,} | {s.get('adrg', '-')} | {s.get('drg', '-')} |"
        )

    lines += [
        "",
        "## 每个方案包含的文件",
        "",
        "| 文件名 | 内容 |",
        "|--------|------|",
        "| `metadata.json` | 方案元信息 |",
        "| `cce_icd_to_mdc.json` | ICD编码 → MDC分组号映射 |",
        "| `mcc_major_complications.json` | MCC严重并发症编码 |",
        "| `cc_complications.json` | CC并发症编码 |",
        "| `ss_valid_procedures.json` | 有效手术/操作编码 |",
        "| `drg_groups.json` | DRG分组定义 |",
    ]

    with open(OUTPUT_BASE / "README.md", 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 70)
    print("  OpenDRG 全量 DRG 方案批量提取器")
    print(f"  方案总数: {len(SCHEME_CATALOG)} 个")
    print("=" * 70)

    # 获取 chunk 映射
    chunk_map = get_chunk_mapping()
    print(f"\nindex.js 中发现 {len(chunk_map)} 个方案映射\n")

    all_results = {}
    success = 0
    fail = 0

    for idx, (scheme_name, info) in enumerate(sorted(SCHEME_CATALOG.items()), 1):
        chunk_id = chunk_map.get(scheme_name)
        if not chunk_id:
            print(f"  [{idx:2}/{len(SCHEME_CATALOG)}] ❌ {scheme_name:<25} 未找到 chunk 映射")
            fail += 1
            continue

        output_dir = OUTPUT_BASE / info["path"]
        result = extract_single_scheme(scheme_name, chunk_id, output_dir)

        if result["status"] == "ok":
            s = result["stats"]
            print(
                f"  [{idx:2}/{len(SCHEME_CATALOG)}] ✅ {scheme_name:<25} "
                f"CCE={s.get('cce',0):>6,}  MCC={s.get('mcc',0):>5,}  "
                f"CC={s.get('cc',0):>5,}  SS={s.get('ss_valid',0):>5,}  "
                f"DRG={s.get('drg',0):>4}"
            )
            all_results[scheme_name] = result
            success += 1
        else:
            print(f"  [{idx:2}/{len(SCHEME_CATALOG)}] ❌ {scheme_name:<25} {result['message']}")
            fail += 1

    # 生成 README
    generate_readme(all_results)

    # 清理旧的未分类目录
    old_dir = OUTPUT_BASE / "chs_drg_20"
    if old_dir.exists() and (OUTPUT_BASE / "national" / "chs_drg_20").exists():
        import shutil
        shutil.rmtree(old_dir)
        print(f"\n已清理旧目录: {old_dir}")

    # 汇总
    print(f"\n{'=' * 70}")
    print(f"  提取完成!  成功: {success}  失败: {fail}")
    print(f"  输出目录: {OUTPUT_BASE}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
