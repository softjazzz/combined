"""只在内存中读取有界、纯数据诊断包；从不解压或执行包内内容。"""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import stat
import struct
import zipfile
import zlib

from .contracts import DiagnosticPackageError, REQUIRED_FILES, validate_documents

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_MEMBER_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_JSON_NODES = 20_000


def _reject(code: str) -> None:
    raise DiagnosticPackageError(code)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _reject("duplicate_json_key")
        result[key] = value
    return result


def _constant(_value: str) -> object:
    _reject("invalid_json_number")


def _json(raw: bytes, remaining_nodes: int) -> tuple[object, int]:
    if raw.startswith(b"\xef\xbb\xbf"):
        _reject("invalid_json_encoding")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant)
    except UnicodeError:
        raise DiagnosticPackageError("invalid_json_encoding") from None
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, DiagnosticPackageError):
            raise
        raise DiagnosticPackageError("invalid_json") from None
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        remaining_nodes -= 1
        if remaining_nodes < 0:
            _reject("json_node_limit")
        if depth > 20:
            _reject("json_depth_limit")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, float):
            # JSON 的 1e999 不经过 parse_constant，也必须拒绝。
            if not math.isfinite(item):
                _reject("invalid_json_number")
    return value, remaining_nodes


def _read_archive(path: str | Path) -> bytes:
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        _reject("archive_size_limit")
    # 禁止自解压前缀、尾随内容、ZIP64尾部、多卷和注释。预检条目数后再构造 ZipFile。
    if len(raw) < 22 or not raw.startswith(b"PK\x03\x04"):
        _reject("invalid_zip")
    end = raw[-22:]
    signature, disk, cd_disk, disk_count, total_count, cd_size, cd_offset, comment = (
        struct.unpack("<4s4H2IH", end)
    )
    if signature != b"PK\x05\x06" or disk or cd_disk or comment:
        _reject("invalid_zip")
    if total_count != len(REQUIRED_FILES) or disk_count != total_count:
        _reject("invalid_zip_members")
    if cd_offset + cd_size != len(raw) - 22:
        _reject("invalid_zip")
    return raw


def _load(path: str | Path) -> dict[str, object]:
    raw = _read_archive(path)
    documents: dict[str, object] = {}
    payloads: dict[str, bytes] = {}
    remaining_nodes = MAX_JSON_NODES
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(REQUIRED_FILES) or set(names) != set(REQUIRED_FILES):
            _reject("invalid_zip_members")
        total = 0
        for member in members:
            if member.orig_filename != member.filename:
                _reject("invalid_zip_members")
            mode = member.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if member.is_dir() or member.external_attr & 0x10 or kind not in (0, stat.S_IFREG):
                _reject("invalid_zip_member_type")
            if member.flag_bits & 1 or member.compress_type not in (
                zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED,
            ):
                _reject("unsupported_zip_encoding")
            if member.file_size > MAX_MEMBER_BYTES:
                _reject("member_size_limit")
            total += member.file_size
            if total > MAX_TOTAL_BYTES:
                _reject("total_size_limit")
            if member.file_size > max(member.compress_size, 1) * 100:
                _reject("compression_ratio_limit")
            with archive.open(member) as stream:
                payload = stream.read(MAX_MEMBER_BYTES + 1)
            if len(payload) > MAX_MEMBER_BYTES or len(payload) != member.file_size:
                _reject("member_size_limit")
            payloads[member.filename] = payload
            value, remaining_nodes = _json(payload, remaining_nodes)
            documents[member.filename] = value
    manifest = documents["manifest.json"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        _reject("invalid_checksum_manifest")
    checksums = manifest["files"]
    expected = set(REQUIRED_FILES) - {"manifest.json"}
    if set(checksums) != expected:
        _reject("invalid_checksum_manifest")
    for name in expected:
        if checksums[name] != hashlib.sha256(payloads[name]).hexdigest():
            _reject("checksum_mismatch")
    # 校验和只能检测与清单不匹配的字节，不证明来源可信，也不证明已脱敏。
    return validate_documents(documents)


def load_diagnostic_package(path: str | Path) -> dict[str, object]:
    """读取并校验六文件诊断包；异常只包含固定安全码，不暴露路径或内容。"""
    try:
        return _load(path)
    except DiagnosticPackageError:
        raise
    except (OSError, ValueError, RuntimeError, EOFError, struct.error,
            zipfile.BadZipFile, zlib.error, NotImplementedError, RecursionError):
        raise DiagnosticPackageError("invalid_zip") from None
