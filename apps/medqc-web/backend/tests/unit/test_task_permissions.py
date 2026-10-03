"""任务权限独立于病历权限，路由入口使用同一任务资源。"""

from inspect import getclosurevars

import pytest

from app.core.permissions import (
    PermissionAction,
    ResourceType,
    UserRole,
    has_permission,
)
from app.routers import tasks


_MANAGER_ACTIONS = {
    PermissionAction.CREATE,
    PermissionAction.READ,
    PermissionAction.UPDATE,
    PermissionAction.DELETE,
    PermissionAction.ANALYZE,
}


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (UserRole.ADMIN, _MANAGER_ACTIONS),
        (UserRole.QC_MANAGER, _MANAGER_ACTIONS),
        (UserRole.QC_STAFF, {PermissionAction.READ, PermissionAction.ANALYZE}),
        (UserRole.DOCTOR, {PermissionAction.READ}),
    ],
)
def test_task_role_matrix(role, allowed):
    user = {"roles": [role]}
    for action in _MANAGER_ACTIONS:
        assert has_permission(user, ResourceType.QC_TASKS, action) is (action in allowed)


def test_task_rights_do_not_expand_medical_record_rights():
    manager = {"roles": [UserRole.QC_MANAGER]}
    doctor = {"roles": [UserRole.DOCTOR]}
    assert not has_permission(manager, ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
    assert not has_permission(manager, ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
    assert has_permission(doctor, ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
    assert not has_permission(doctor, ResourceType.QC_TASKS, PermissionAction.CREATE)


# 任务内人工缺陷补录写入的是缺陷（质控结果）资源，沿用缺陷入口的 QC_RESULTS 权限；
# 受领人范围由服务层另行校验。例外必须逐条登记，新增路由默认仍须使用任务资源。
_NON_TASK_RESOURCE_ROUTES = {
    ("POST", "/{task_id}/records/{task_record_id}/manual-defects"): (
        ResourceType.QC_RESULTS,
        PermissionAction.CREATE,
    ),
    ("GET", "/{task_id}/records/{task_record_id}/manual-document-options"): (
        ResourceType.QC_RESULTS,
        PermissionAction.CREATE,
    ),
}


def test_all_task_routes_use_task_permission_resource():
    seen_exceptions = set()
    for route in tasks.router.routes:
        permission = getclosurevars(route.endpoint).nonlocals
        for method in route.methods:
            key = (method, route.path.removeprefix(tasks.router.prefix))
            if key in _NON_TASK_RESOURCE_ROUTES:
                seen_exceptions.add(key)
                expected = _NON_TASK_RESOURCE_ROUTES[key]
                assert (permission["resource"], permission["action"]) == expected, key
            else:
                assert permission["resource"] == ResourceType.QC_TASKS, key
    assert seen_exceptions == set(_NON_TASK_RESOURCE_ROUTES)


def test_manual_defect_create_right_matches_task_analyze_right():
    """人工缺陷补录不得让无任务处理权的角色获得写入口。"""
    for role in (UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.QC_STAFF, UserRole.DOCTOR):
        user = {"roles": [role]}
        assert has_permission(user, ResourceType.QC_RESULTS, PermissionAction.CREATE) is (
            has_permission(user, ResourceType.QC_TASKS, PermissionAction.ANALYZE)
        ), role


@pytest.mark.parametrize(
    ("endpoint", "action"),
    [
        (tasks.create_task, PermissionAction.CREATE),
        (tasks.execute_sampling, PermissionAction.UPDATE),
        (tasks.assign_task, PermissionAction.UPDATE),
        (tasks.cancel_task, PermissionAction.UPDATE),
        (tasks.delete_task, PermissionAction.DELETE),
        (tasks.update_task, PermissionAction.ANALYZE),
        (tasks.start_task_record, PermissionAction.ANALYZE),
        (tasks.start_task_qc_run, PermissionAction.ANALYZE),
        (tasks.re_analyze_task, PermissionAction.ANALYZE),
        (tasks.sync_saved_task_records, PermissionAction.UPDATE),
        (tasks.latest_saved_task_record_sync, PermissionAction.READ),
        (tasks.get_saved_task_record_sync, PermissionAction.READ),
    ],
)
def test_task_mutation_routes_require_expected_action(endpoint, action):
    assert getclosurevars(endpoint).nonlocals["action"] == action
