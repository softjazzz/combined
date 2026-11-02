"""新任务调度开关的唯一owner；原子文件配置，不修改环境、任务或数据库。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from ...core.settings import get_settings
from .config import RabbitMQSettings


class DispatchControlError(ValueError):
    pass


class DispatchControlConflict(DispatchControlError):
    pass


class DispatchControl(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    rabbitmq_enabled: StrictBool
    revision: int = Field(default=0, ge=0, strict=True)
    updated_at: str | None = None
    updated_by: str | None = None


def state_directory(settings=None) -> Path:
    cfg = settings if settings is not None else get_settings()
    configured = getattr(cfg, 'QC_DISPATCH_STATE_DIR', None)
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / 'data' / 'qc_dispatch_control'


def load_control(settings=None) -> tuple[DispatchControl, str]:
    cfg = settings if settings is not None else get_settings()
    path = state_directory(cfg) / 'settings.json'
    try:
        if path.exists():
            return DispatchControl.model_validate_json(path.read_text(encoding='utf-8')), 'file'
    except (OSError, ValueError) as exc:
        raise DispatchControlError('质控运行配置无法读取，请检查配置文件') from exc
    mode = getattr(cfg, 'QC_TASK_DISPATCH_MODE', 'legacy')
    if mode not in ('legacy', 'rabbitmq'):
        raise DispatchControlError('质控任务调度模式无效')
    return DispatchControl(rabbitmq_enabled=mode == 'rabbitmq'), 'environment'


def effective_dispatch_mode(settings=None) -> Literal['legacy', 'rabbitmq']:
    current, _ = load_control(settings)
    return 'rabbitmq' if current.rabbitmq_enabled else 'legacy'


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise DispatchControlError('质控运行配置保存失败') from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def _write_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'settings.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def save_control(*, enabled: bool, expected_revision: int, actor: str, settings=None) -> DispatchControl:
    cfg = settings if settings is not None else get_settings()
    try:
        with _write_lock(state_directory(cfg)):
            current, _ = load_control(cfg)
            if current.revision != expected_revision:
                raise DispatchControlConflict('配置已被其他管理员更新，请刷新后重试')
            updated = DispatchControl(rabbitmq_enabled=enabled, revision=current.revision + 1,
                updated_at=datetime.now(timezone.utc).isoformat(), updated_by=actor)
            atomic_write(state_directory(cfg) / 'settings.json', updated.model_dump())
            return updated
    except OSError as exc:
        raise DispatchControlError('质控运行配置正在更新或无法保存，请稍后重试') from exc


def rabbitmq_settings(settings) -> RabbitMQSettings:
    return RabbitMQSettings.from_env({name: str(getattr(settings, name, '') or '') for name in (
        'QC_RABBITMQ_URL', 'QC_RABBITMQ_EXCHANGE', 'QC_RABBITMQ_QUEUE', 'QC_RABBITMQ_DEAD_QUEUE')})


def deployment_identity(settings, broker: RabbitMQSettings | None = None) -> str:
    mq = broker if broker is not None else rabbitmq_settings(settings)
    values = [mq.url, mq.exchange, mq.queue, mq.dead_queue,
              str(getattr(settings, 'DATABASE_URL', '') or ''),
              str(getattr(settings, 'DB_SCHEMA_MODE', '')),
              str(getattr(settings, 'DB_SEARCH_PATH', ''))]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()
