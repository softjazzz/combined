from __future__ import annotations

from fastapi import Query


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20

STANDARD_MAX_PAGE_SIZE = 100
HEAVY_MAX_PAGE_SIZE = 200
REPORT_SCAN_LIMIT = 1000


def page_param(default: int = DEFAULT_PAGE, description: str = "页码"):
    return Query(default=default, ge=1, description=description)


def page_size_param(
    default: int = DEFAULT_PAGE_SIZE,
    max_value: int = STANDARD_MAX_PAGE_SIZE,
    description: str = "每页条数",
):
    return Query(default=default, ge=1, le=max_value, description=description)


def limit_param(
    default: int = DEFAULT_PAGE_SIZE,
    max_value: int = STANDARD_MAX_PAGE_SIZE,
    description: str = "返回条数",
):
    return Query(default=default, ge=1, le=max_value, description=description)


def offset_param(default: int = 0, description: str = "分页偏移"):
    return Query(default=default, ge=0, description=description)
