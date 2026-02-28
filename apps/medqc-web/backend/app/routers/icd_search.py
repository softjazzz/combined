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

_icd10_data: List[dict] = []
_icd9cm3_data: List[dict] = []
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
    global _icd10_data, _icd9cm3_data, _initialized

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
            logger.info(f"✅ ICD-10 编码库: {len(_icd10_data)} 条")
    else:
        logger.warning(f"⚠️ ICD-10 文件未找到: {icd10_path}")

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
        results.extend(_search_dataset(_icd10_data, q, 'icd10'))
    if type in ('icd9cm3', 'all'):
        results.extend(_search_dataset(_icd9cm3_data, q, 'icd9cm3'))

    # 按匹配度排序
    results.sort(key=lambda x: -x['_score'])
    total = len(results)

    # 分页
    page = results[offset:offset + limit]

    # 清理内部字段
    for r in page:
        del r['_score']

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
