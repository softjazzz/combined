"""仅保存会话归属、业务上下文和对象定位；DSH 独占执行历史。"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException

from .business_schemas import BusinessContext


def owner_id(user: dict) -> str:
    owner = str(user.get("id") or user.get("user_id") or "").strip()
    if not owner:
        raise HTTPException(403, "账号缺少会话身份")
    return owner


class BusinessSessionStore:
    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.RLock()

    def path(self, session_id: str) -> Path:
        try:
            normalized = str(UUID(session_id))
        except ValueError as exc:
            raise HTTPException(404, "助手会话不存在") from exc
        return self.root / f"{normalized}.json"

    def write(self, metadata: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.path(metadata["session_id"])
        temporary = target.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        # Windows 文件扫描短暂占用目标时保留原子替换，不能退化为覆盖写。
        for attempt in range(6):
            try:
                os.replace(temporary, target)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.01 * (attempt + 1))

    def create(self, user: dict, context: BusinessContext) -> dict:
        metadata = {
            "session_id": str(uuid4()), "owner_id": owner_id(user),
            "context": context.model_dump(exclude_none=True), "references": {},
        }
        with self.lock:
            self.write(metadata)
        return metadata

    def get(self, session_id: str, user: dict) -> dict:
        with self.lock:
            path = self.path(session_id)
            if not path.is_file():
                raise HTTPException(404, "助手会话不存在")
            metadata = json.loads(path.read_text(encoding="utf-8"))
            if metadata["owner_id"] != owner_id(user):
                raise HTTPException(404, "助手会话不存在")
            return metadata

    def bind(self, session_id: str, user: dict, reference_id: str, locator: dict) -> None:
        # 只记录可回查对象的坐标，不复制原文、结果事实或模型执行事件。
        with self.lock:
            metadata = self.get(session_id, user)
            metadata["references"][reference_id] = locator
            self.write(metadata)


_store = BusinessSessionStore(Path(__file__).resolve().parents[3] / ".tmp" / "business-agent" / "metadata")


def get_business_store() -> BusinessSessionStore:
    return _store
