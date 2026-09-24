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


def test_all_task_routes_use_task_permission_resource():
    for route in tasks.router.routes:
        permission = getclosurevars(route.endpoint).nonlocals
        assert permission["resource"] == ResourceType.QC_TASKS, route.path


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
