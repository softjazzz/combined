"""匿名数据验证 ZIP/JSON 安全边界；业务合同由专门合同测试覆盖。"""

import hashlib
import json
import stat
import struct
import zipfile

import pytest

from app.services.qc_diagnostics import package
from app.services.qc_diagnostics.contracts import DiagnosticPackageError, REQUIRED_FILES


def _payloads():
    data = {name: b"{}" for name in REQUIRED_FILES if name != "manifest.json"}
    return data


def _write(tmp_path, data=None, *, compression=zipfile.ZIP_STORED, metadata=None):
    data = _payloads() if data is None else dict(data)
    checksums = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}
    data = {"manifest.json": json.dumps({"files": checksums}).encode(), **data}
    target = tmp_path / "anonymous.zip"
    with zipfile.ZipFile(target, "w", compression=compression) as archive:
        for name, raw in data.items():
            info = metadata if metadata and metadata.filename == name else name
            archive.writestr(info, raw)
    return target


@pytest.fixture(autouse=True)
def isolate_contract(monkeypatch):
    monkeypatch.setattr(package, "validate_documents", lambda documents: documents)


def test_accepts_valid_integrity_without_extracting(tmp_path, monkeypatch):
    monkeypatch.setattr(zipfile.ZipFile, "extractall", lambda *_: pytest.fail("extracted"))
    assert set(package.load_diagnostic_package(_write(tmp_path))) == set(REQUIRED_FILES)


@pytest.mark.parametrize("name", ["../issue.json", "/issue.json", "C:/issue.json", "issue.json:x", "extra.py", "folder/"])
def test_rejects_unknown_or_path_member(tmp_path, name):
    data = _payloads()
    data[name] = data.pop("issue.json")
    with pytest.raises(DiagnosticPackageError, match="invalid_zip_members"):
        package.load_diagnostic_package(_write(tmp_path, data))


def test_rejects_duplicate_member(tmp_path):
    target = _write(tmp_path)
    with pytest.warns(UserWarning), zipfile.ZipFile(target, "a") as archive:
        archive.writestr("issue.json", b"{}")
    with pytest.raises(DiagnosticPackageError, match="invalid_zip_members"):
        package.load_diagnostic_package(target)


@pytest.mark.parametrize("kind", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFDIR])
def test_rejects_special_member(tmp_path, kind):
    info = zipfile.ZipInfo("issue.json")
    info.create_system = 3
    info.external_attr = (kind | 0o600) << 16
    with pytest.raises(DiagnosticPackageError, match="invalid_zip_member_type"):
        package.load_diagnostic_package(_write(tmp_path, metadata=info))


@pytest.mark.parametrize("raw, code", [
    (b'{"x":1,"x":2}', "duplicate_json_key"),
    (b'{"x":NaN}', "invalid_json_number"),
    (b'{"x":Infinity}', "invalid_json_number"),
    (b'{"x":1e999}', "invalid_json_number"),
    (b'{invalid', "invalid_json"),
    (b'\xef\xbb\xbf{}', "invalid_json_encoding"),
    (b'"\xff"', "invalid_json_encoding"),
    (b'[' * 22 + b'0' + b']' * 22, "json_depth_limit"),
    (b'[' + b'0,' * 20000 + b'0]', "json_node_limit"),
], ids=["duplicate", "nan", "infinity", "overflow", "syntax", "bom", "utf8", "depth", "nodes"])
def test_rejects_invalid_json(tmp_path, raw, code):
    data = _payloads()
    data["issue.json"] = raw
    with pytest.raises(DiagnosticPackageError, match=code):
        package.load_diagnostic_package(_write(tmp_path, data))


def test_rejects_oversized_member(tmp_path):
    data = _payloads()
    data["issue.json"] = b" " * (package.MAX_MEMBER_BYTES + 1)
    with pytest.raises(DiagnosticPackageError, match="member_size_limit"):
        package.load_diagnostic_package(_write(tmp_path, data))


def test_rejects_compression_bomb(tmp_path):
    data = _payloads()
    data["issue.json"] = b'"' + b"a" * 100000 + b'"'
    with pytest.raises(DiagnosticPackageError, match="compression_ratio_limit"):
        package.load_diagnostic_package(_write(tmp_path, data, compression=zipfile.ZIP_DEFLATED))


def test_rejects_total_size(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "MAX_TOTAL_BYTES", 4)
    with pytest.raises(DiagnosticPackageError, match="total_size_limit"):
        package.load_diagnostic_package(_write(tmp_path))


def test_rejects_archive_size(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "MAX_ARCHIVE_BYTES", 4)
    with pytest.raises(DiagnosticPackageError, match="archive_size_limit"):
        package.load_diagnostic_package(_write(tmp_path))


def test_rejects_crc_corruption(tmp_path):
    target = _write(tmp_path)
    with zipfile.ZipFile(target) as archive:
        info = archive.getinfo("issue.json")
        start = info.header_offset
    raw = bytearray(target.read_bytes())
    name_len, extra_len = struct.unpack_from("<HH", raw, start + 26)
    raw[start + 30 + name_len + extra_len] ^= 1
    target.write_bytes(raw)
    with pytest.raises(DiagnosticPackageError, match="invalid_zip"):
        package.load_diagnostic_package(target)


def test_rejects_valid_zip_with_checksum_mismatch(tmp_path):
    target = _write(tmp_path)
    with zipfile.ZipFile(target) as archive:
        data = {name: archive.read(name) for name in REQUIRED_FILES}
    data["issue.json"] = b'{"changed":true}'
    with zipfile.ZipFile(target, "w") as archive:
        for name, raw in data.items():
            archive.writestr(name, raw)
    with pytest.raises(DiagnosticPackageError, match="checksum_mismatch"):
        package.load_diagnostic_package(target)


@pytest.mark.parametrize("prefix,suffix", [(b"MZ", b""), (b"", b"executable")])
def test_rejects_prefix_or_trailing_content(tmp_path, prefix, suffix):
    target = _write(tmp_path)
    target.write_bytes(prefix + target.read_bytes() + suffix)
    with pytest.raises(DiagnosticPackageError, match="invalid_zip"):
        package.load_diagnostic_package(target)


def test_missing_path_is_not_exposed(tmp_path):
    with pytest.raises(DiagnosticPackageError) as caught:
        package.load_diagnostic_package(tmp_path / "private-patient-name.zip")
    assert str(caught.value) == "invalid_zip"


def test_rejects_encrypted_flag(tmp_path):
    target = _write(tmp_path)
    raw = bytearray(target.read_bytes())
    central = raw.index(b"PK\x01\x02")
    struct.pack_into("<H", raw, central + 8, 1)
    target.write_bytes(raw)
    with pytest.raises(DiagnosticPackageError, match="unsupported_zip_encoding"):
        package.load_diagnostic_package(target)


def test_rejects_unapproved_compression(tmp_path):
    with pytest.raises(DiagnosticPackageError, match="unsupported_zip_encoding"):
        package.load_diagnostic_package(_write(tmp_path, compression=zipfile.ZIP_BZIP2))


def test_accepts_normal_deflate(tmp_path):
    loaded = package.load_diagnostic_package(_write(tmp_path, compression=zipfile.ZIP_DEFLATED))
    assert loaded["issue.json"] == {}
