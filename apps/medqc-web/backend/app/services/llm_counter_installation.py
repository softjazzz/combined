"""精确Counter的应用侧装配边界；不实现Tokenizer，也不猜DSH组件接口。"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import threading
from typing import Callable, Mapping, Sequence

from . import llm_token_budget as budget


@dataclass(frozen=True)
class TokenVector:
    payload: dict
    expected_tokens: int


class _InstalledCounter:
    def __init__(self, capability, signature, count, validated_vectors):
        self.capability = capability
        self.signature = signature
        self.validated_vectors = validated_vectors
        self._count = count
        self._lock = threading.RLock()
        self._closed = False

    def __call__(self, payload):
        with self._lock:
            if self._closed:
                raise ValueError('counter_closed')
            copied = deepcopy(payload)
            expected = deepcopy(copied)
            value = self._count(copied)
            if copied != expected or type(value) is not int or value < 0:
                raise ValueError('counter_result_invalid')
            return value

    def close(self):
        with self._lock:
            budget.unregister_counter(self.capability.counter_id, self.capability.counter_revision, self)
            self._closed = True
            self._count = None


class CounterInstaller:
    """每个Runtime拥有一份。显式装配一次，关闭后不再接受迟到的计量。"""
    def __init__(self):
        self._lock = threading.RLock()
        self._installed = {}
        self._closed = False

    def install(self, *, capability: budget.BudgetCapability, resource_root: Path,
                file_hashes: Mapping[str, str], factory: Callable,
                vectors: Sequence[TokenVector]):
        # file_hashes必须来自已人工核对的交付，不以现场自算哈希冒充可信预期。
        with self._lock:
            try:
                return self._install(capability, resource_root, file_hashes, factory, vectors)
            except budget.BudgetError as error:
                budget.note_budget_failure(error)
                raise
            except Exception:
                # 组件异常不准回显payload、原文、资源路径或任意上游错误。
                error = budget.BudgetError(budget.BudgetVerdict('COUNT_UNAVAILABLE',
                    'counter_installation_failed', capability.profile, capability.model))
                budget.note_budget_failure(error)
                raise error from None

    def _install(self, cap, root, hashes, factory, vectors):
        if self._closed or not cap.verified or not cap.verified_message_shapes or not callable(factory):
            raise ValueError('counter_not_approved')
        root = Path(root).resolve(strict=True)
        if not root.is_dir() or not hashes or not vectors:
            raise ValueError('counter_materials_missing')
        expected_identity = budget.CounterIdentity(**{
            field: getattr(cap, field) for field in budget.CounterIdentity.__dataclass_fields__})
        copied_vectors = deepcopy(tuple(vectors))
        signature = (expected_identity, str(root), tuple(sorted(hashes.items())), copied_vectors)
        key = cap.counter_id, cap.counter_revision
        existing = self._installed.get(key)
        if existing is not None:
            if existing.signature != signature:
                raise ValueError('counter_installation_conflict')
            return existing
        for relative, digest in hashes.items():
            if not isinstance(relative, str) or not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
                raise ValueError('counter_manifest_invalid')
            path = (root / relative).resolve(strict=True)
            if Path(relative).is_absolute() or root not in path.parents or not path.is_file():
                raise ValueError('counter_resource_outside_root')
            # 所有文件先验证完，再调用经审查的适配factory；不自动import交付文件。
            with path.open('rb') as source:
                actual = _sha256(source)
            if actual != digest:
                raise ValueError('counter_resource_hash_mismatch')
        actual_identity, count = factory(root)
        if actual_identity != expected_identity or not callable(count):
            raise ValueError('counter_identity_mismatch')
        installed = _InstalledCounter(cap, signature, count, len(copied_vectors))
        for vector in copied_vectors:
            if (not isinstance(vector, TokenVector) or type(vector.expected_tokens) is not int
                    or vector.expected_tokens < 0 or not isinstance(vector.payload, dict)):
                raise ValueError('counter_vector_invalid')
            messages = vector.payload.get('messages')
            if (not isinstance(messages, list) or not messages
                    or any(not isinstance(item, dict) or set(item) != {'role', 'content'}
                           or not isinstance(item.get('content'), str) for item in messages)):
                raise ValueError('counter_vector_shape_unverified')
            shape = '|'.join(item.get('role', '') for item in messages)
            if shape not in cap.verified_message_shapes or installed(vector.payload) != vector.expected_tokens:
                raise ValueError('counter_vector_mismatch')
        budget.register_counter(*key, actual_identity, installed)
        self._installed[key] = installed
        return installed

    def close(self):
        with self._lock:
            for installed in self._installed.values():
                installed.close()
            self._installed.clear()
            self._closed = True


def _sha256(source):
    digest = hashlib.sha256()
    for block in iter(lambda: source.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()
