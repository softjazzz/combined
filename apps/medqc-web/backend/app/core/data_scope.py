"""工作台全院质控数据的可见范围（数据范围层授权）。

首页、统计、结果下钻等接口读取的是全院病历（含患者姓名与三坐标），
仅校验登录不足以约束数据范围。本模块是这些接口唯一的范围判定入口：

- 全院范围角色：admin / qc_manager / sync_admin / super_admin，可按请求科室筛选；
- 科室范围角色：doctor，强制限定为账号 ``department``，与病历科室精确相等
  （与任务分配 by_department 口径一致）；账号未配置科室时失败关闭；
- 其他角色：无权读取。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

from fastapi import HTTPException, status

FULL_SCOPE_ROLES = frozenset({"admin", "qc_manager", "sync_admin", "super_admin"})
DEPARTMENT_SCOPE_ROLES = frozenset({"doctor"})


@dataclass(frozen=True)
class WorkstationDataScope:
    hospital_scope: Literal["all", "department"]
    # 实际生效的科室筛选；全院范围且未指定科室时为 None
    department: Optional[str]


def _user_roles(current_user: Mapping[str, Any] | None) -> set[str]:
    raw = (current_user or {}).get("roles") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(role).strip().lower() for role in raw if str(role).strip()}


def resolve_workstation_data_scope(
    current_user: Mapping[str, Any] | None,
    requested_department: Optional[str],
) -> WorkstationDataScope:
    """按当前用户解析数据范围；无权或范围不明时抛出 403。"""

    requested = str(requested_department or "").strip() or None
    roles = _user_roles(current_user)

    if roles & FULL_SCOPE_ROLES:
        return WorkstationDataScope(hospital_scope="all", department=requested)

    if roles & DEPARTMENT_SCOPE_ROLES:
        own_department = str((current_user or {}).get("department") or "").strip()
        if not own_department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号未配置科室，无法确定可查看的数据范围",
            )
        if requested and requested != own_department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看其他科室的数据",
            )
        return WorkstationDataScope(
            hospital_scope="department", department=own_department
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="当前角色无权查看全院质控数据",
    )
