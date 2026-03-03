"""
ICD 编码搜索 API

基于本地 ICD-10 / ICD-9-CM-3 编码库 JSON 文件，提供高速搜索服务。
支持：中文名称、编码、拼音首字母匹配。
数据来源：backend/data/icd10_diagnoses.json + icd9cm3_procedures.json
"""

from fastapi import APIRouter, Query
from typing import List, Optional
import json
import os
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/icd", tags=["ICD 编码查询"])

# ==================== 数据缓存 ====================

_icd10_data: List[dict] = []          # 医保版
_icd10_clinical_data: List[dict] = [] # 国临版
_icd9cm3_data: List[dict] = []
_icd10_tree: Optional[dict] = None
_icd9cm3_tree: Optional[dict] = None
_code_mapping: Optional[dict] = None
_initialized: bool = False

# 简易拼音首字母映射表（覆盖常见3500字）
_PINYIN_MAP: dict = {}


def _init_pinyin_map():
    """初始化简易拼音首字母映射（避免依赖 pypinyin 库）"""
    global _PINYIN_MAP
    # 按拼音首字母的 Unicode 区间粗略映射
    # 这里用更可靠的方式：尝试导入 pypinyin，否则跳过拼音功能
    try:
        from pypinyin import lazy_pinyin, Style
        _PINYIN_MAP['_available'] = True
        _PINYIN_MAP['_lazy_pinyin'] = lazy_pinyin
        _PINYIN_MAP['_Style'] = Style
        logger.info("✅ pypinyin 可用，启用拼音搜索")
    except ImportError:
        _PINYIN_MAP['_available'] = False
        logger.info("ℹ️ pypinyin 未安装，跳过拼音搜索功能")


def _get_pinyin_initials(text: str) -> str:
    """获取拼音首字母"""
    if not _PINYIN_MAP.get('_available'):
        return ''
    try:
        initials = _PINYIN_MAP['_lazy_pinyin'](text, style=_PINYIN_MAP['_Style'].FIRST_LETTER)
        return ''.join(initials).lower()
    except Exception:
        return ''


def _load_data():
    """懒加载编码库，首次请求时触发"""
    global _icd10_data, _icd10_clinical_data, _icd9cm3_data, _icd10_tree, _icd9cm3_tree, _code_mapping, _initialized

    if _initialized:
        return

    _init_pinyin_map()

    # __file__ = app/routers/icd_search.py
    # data 在 backend/data/ 目录（即 app 的上一级）
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')

    # ICD-10
    icd10_path = os.path.join(data_dir, 'icd10_diagnoses.json')
    if os.path.exists(icd10_path):
        with open(icd10_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            for item in raw:
                item['pinyin'] = _get_pinyin_initials(item.get('name', ''))
                item['name_lower'] = item.get('name', '').lower()
                item['code_lower'] = item.get('code', '').lower()
            _icd10_data = raw
            logger.info(f"✅ ICD-10 医保版: {len(_icd10_data)} 条")
    else:
        logger.warning(f"⚠️ ICD-10 医保版文件未找到: {icd10_path}")

    # ICD-10 国临版
    icd10_cl_path = os.path.join(data_dir, 'icd10_clinical_diagnoses.json')
    if os.path.exists(icd10_cl_path):
        with open(icd10_cl_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            for item in raw:
                item['pinyin'] = _get_pinyin_initials(item.get('name', ''))
                item['name_lower'] = item.get('name', '').lower()
                item['code_lower'] = item.get('code', '').lower()
            _icd10_clinical_data = raw
            logger.info(f"✅ ICD-10 国临版: {len(_icd10_clinical_data)} 条")

    # ICD-9-CM-3
    icd9_path = os.path.join(data_dir, 'icd9cm3_procedures.json')
    if os.path.exists(icd9_path):
        with open(icd9_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            for item in raw:
                item['pinyin'] = _get_pinyin_initials(item.get('name', ''))
                item['name_lower'] = item.get('name', '').lower()
                item['code_lower'] = item.get('code', '').lower()
            _icd9cm3_data = raw
            logger.info(f"✅ ICD-9-CM-3 编码库: {len(_icd9cm3_data)} 条")
    else:
        logger.warning(f"⚠️ ICD-9-CM-3 文件未找到: {icd9_path}")

    # 加载层级 JSON（用于树形浏览）
    icd10_tree_path = os.path.join(data_dir, 'icd10_hierarchical.json')
    if os.path.exists(icd10_tree_path):
        with open(icd10_tree_path, 'r', encoding='utf-8') as f:
            _icd10_tree = json.load(f)
        logger.info(f"✅ ICD-10 层级数据: {len(_icd10_tree.get('chapters', []))} 章")

    icd9_tree_path = os.path.join(data_dir, 'icd9cm3_hierarchical.json')
    if os.path.exists(icd9_tree_path):
        with open(icd9_tree_path, 'r', encoding='utf-8') as f:
            _icd9cm3_tree = json.load(f)
        logger.info(f"✅ ICD-9 层级数据: {len(_icd9cm3_tree.get('chapters', []))} 章")

    # 加载国临↔医保编码映射
    mapping_path = os.path.join(data_dir, 'icd10_code_mapping.json')
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r', encoding='utf-8') as f:
            _code_mapping = json.load(f)
        logger.info(f"✅ 编码映射: 总{_code_mapping.get('total', 0)}条, 不同{_code_mapping.get('diff_count', 0)}条")

    _initialized = True


def _search_dataset(data: List[dict], query: str, ds_type: str) -> List[dict]:
    """在单个数据集中搜索"""
    results = []
    query_lower = query.lower()
    is_alpha = query.isascii() and query.isalpha()

    for item in data:
        score = 0

        # 1. 编码完全匹配
        if item['code_lower'] == query_lower:
            score = 100
        # 2. 编码前缀匹配
        elif item['code_lower'].startswith(query_lower):
            score = 90
        # 3. 中文名称包含
        elif query_lower in item['name_lower']:
            # 名称以关键词开头得更高分
            if item['name_lower'].startswith(query_lower):
                score = 85
            else:
                score = 80
        # 4. 拼音首字母匹配（仅当输入是纯字母时）
        elif is_alpha and item.get('pinyin') and query_lower in item['pinyin']:
            if item['pinyin'].startswith(query_lower):
                score = 75
            else:
                score = 60
        # 5. 编码部分包含
        elif query_lower in item['code_lower']:
            score = 50

        if score > 0:
            results.append({
                'code': item['code'],
                'name': item['name'],
                'type': ds_type,
                '_score': score,
            })

    return results


# ==================== API 路由 ====================

@router.get("/search")
async def search_icd_codes(
    q: str = Query(..., min_length=1, description="搜索关键词（名称/编码/拼音首字母）"),
    type: str = Query("all", description="编码类型: icd10 / icd9cm3 / all"),
    version: str = Query("insurance", description="编码版本: clinical(国临版) / insurance(医保版)"),
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, description="分页偏移"),
):
    """
    搜索 ICD 编码

    支持：
    - 中文疾病/手术名称搜索
    - ICD 编码搜索（精确或前缀匹配）
    - 拼音首字母搜索（如 jxqbyxgsi → 急性前壁...）
    """
    _load_data()

    results = []

    if type in ('icd10', 'all'):
        # 根据版本选择数据源
        icd10_source = _icd10_clinical_data if version == 'clinical' and _icd10_clinical_data else _icd10_data
        results.extend(_search_dataset(icd10_source, q, 'icd10'))
    if type in ('icd9cm3', 'all'):
        results.extend(_search_dataset(_icd9cm3_data, q, 'icd9cm3'))

    # 按匹配度排序
    results.sort(key=lambda x: -x['_score'])
    total = len(results)

    # 分页
    page = results[offset:offset + limit]

    # 清理内部字段 + 附加映射信息
    for r in page:
        del r['_score']
        # 为 ICD-10 结果附加另一版本映射
        if r['type'] == 'icd10' and _code_mapping:
            code = r['code']
            if version == 'clinical':
                # 当前是国临版 → 显示医保版对应
                lookup = _code_mapping.get('clinical_to_insurance', {})
                mapped_label = '医保版'
            else:
                # 当前是医保版 → 显示国临版对应
                lookup = _code_mapping.get('insurance_to_clinical', {})
                mapped_label = '国临版'
            if code in lookup:
                m = lookup[code]
                r['mapped_code'] = m['code']
                r['mapped_name'] = m['name']
                r['mapped_version'] = mapped_label
                r['is_diff'] = m.get('diff', False)

    return {
        'success': True,
        'data': {
            'items': page,
            'total': total,
            'query': q,
            'type': type,
        }
    }


@router.get("/stats")
async def get_icd_stats():
    """获取编码库统计信息"""
    _load_data()
    return {
        'success': True,
        'data': {
            'icd10_count': len(_icd10_data),
            'icd9cm3_count': len(_icd9cm3_data),
            'total': len(_icd10_data) + len(_icd9cm3_data),
        }
    }


@router.get("/lookup/{code}")
async def lookup_icd_code(code: str):
    """根据编码精确查询，返回名称和类型"""
    _load_data()

    code_lower = code.strip().lower()

    # 先查 ICD-10
    for item in _icd10_data:
        if item['code_lower'] == code_lower:
            return {
                'success': True,
                'data': {
                    'code': item['code'],
                    'name': item['name'],
                    'type': 'icd10',
                }
            }

    # 再查 ICD-9-CM-3
    for item in _icd9cm3_data:
        if item['code_lower'] == code_lower:
            return {
                'success': True,
                'data': {
                    'code': item['code'],
                    'name': item['name'],
                    'type': 'icd9cm3',
                }
            }

    return {
        'success': False,
        'error': f'编码 {code} 未找到',
    }


# ==================== 树形浏览 API ====================

@router.get("/tree")
async def get_icd_tree(
    type: str = Query("icd10", description="编码类型: icd10 / icd9cm3"),
):
    """
    获取 ICD 编码树的章级结构（懒加载根节点）

    返回章列表，每章只含 章号/名称/代码范围 + sections 摘要（不含叶子节点）
    """
    _load_data()

    tree = _icd10_tree if type == 'icd10' else _icd9cm3_tree
    if not tree:
        return {'success': False, 'error': f'{type} 层级数据未加载'}

    # 只返回章级 + 节级摘要，不返回深层叶子
    chapters = []
    for ch in tree.get('chapters', []):
        ch_item = {
            'key': f"ch-{ch['chapter']}",
            'title': f"章{ch['chapter']} {ch.get('name', '')}",
            'code_range': ch.get('code_range', ''),
            'isLeaf': False,
            'children': []
        }
        # 添加节级
        for sec in ch.get('sections', ch.get('categories', [])):
            sec_range = sec.get('code_range', sec.get('code', ''))
            sec_name = sec.get('name', '')
            sec_item = {
                'key': f"sec-{sec_range}",
                'title': f"{sec_range} {sec_name}",
                'code_range': sec_range,
                'isLeaf': False,
            }
            ch_item['children'].append(sec_item)
        chapters.append(ch_item)

    return {
        'success': True,
        'data': {
            'type': type,
            'version': tree.get('version', ''),
            'chapters': chapters,
        }
    }


@router.get("/tree/children")
async def get_icd_tree_children(
    type: str = Query("icd10", description="编码类型: icd10 / icd9cm3"),
    parent_key: str = Query(..., description="父节点 key，如 sec-A00-A09 或 cat-A00"),
):
    """
    懒加载树节点的子元素

    - parent_key = sec-{code_range} → 返回该节下的类目
    - parent_key = cat-{code} → 返回该类目下的亚目/诊断
    - parent_key = sub-{code} → 返回该亚目下的最终诊断/手术
    """
    _load_data()

    tree = _icd10_tree if type == 'icd10' else _icd9cm3_tree
    if not tree:
        return {'success': False, 'error': f'{type} 层级数据未加载'}

    parts = parent_key.split('-', 1)
    if len(parts) != 2:
        return {'success': False, 'error': f'无效的 parent_key: {parent_key}'}

    node_type, node_id = parts[0], parts[1]
    children = []
    items_key = 'diagnoses' if type == 'icd10' else 'procedures'

    for ch in tree.get('chapters', []):
        sections = ch.get('sections', ch.get('categories', []))
        for sec in sections:
            sec_range = sec.get('code_range', sec.get('code', ''))

            if node_type == 'sec' and sec_range == node_id:
                # 返回该节下的类目
                for cat in sec.get('categories', sec.get('subcategories', [])):
                    cat_code = cat.get('code', '')
                    cat_name = cat.get('name', '')
                    has_children = bool(cat.get('subcategories') or cat.get(items_key))
                    children.append({
                        'key': f"cat-{cat_code}",
                        'title': f"{cat_code} {cat_name}",
                        'code': cat_code,
                        'isLeaf': not has_children,
                    })
                return {'success': True, 'data': {'children': children}}

            # 深入类目层
            for cat in sec.get('categories', sec.get('subcategories', [])):
                cat_code = cat.get('code', '')

                if node_type == 'cat' and cat_code == node_id:
                    # 返回亚目
                    for sub in cat.get('subcategories', []):
                        sub_code = sub.get('code', '')
                        sub_name = sub.get('name', '')
                        has_items = bool(sub.get(items_key))
                        children.append({
                            'key': f"sub-{sub_code}",
                            'title': f"{sub_code} {sub_name}",
                            'code': sub_code,
                            'isLeaf': not has_items,
                        })
                    return {'success': True, 'data': {'children': children}}

                # 深入亚目层
                for sub in cat.get('subcategories', []):
                    sub_code = sub.get('code', '')

                    if node_type == 'sub' and sub_code == node_id:
                        # 返回最终诊断/手术
                        for item in sub.get(items_key, []):
                            children.append({
                                'key': f"leaf-{item.get('code', '')}",
                                'title': f"{item.get('code', '')} {item.get('name', '')}",
                                'code': item.get('code', ''),
                                'name': item.get('name', ''),
                                'isLeaf': True,
                            })
                        return {'success': True, 'data': {'children': children}}

    return {'success': True, 'data': {'children': children}}
