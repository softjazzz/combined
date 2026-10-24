"""PR8 只离线验证：禁读 dotenv、禁网络、禁非 SQLite 连接，不加载应用 lifespan。"""

import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import dotenv
from pydantic_settings import DotEnvSettingsSource
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

_socket_connect = socket.socket.connect
_socketpair_code = getattr(socket.socketpair, "__code__", None)


def deny_network(*_args, **_kwargs):
    raise RuntimeError("PR8 离线测试禁止网络与模型请求")


def guarded_connect(sock, address):
    # Windows asyncio 用标准库 socketpair 创建内部唤醒管道，不是应用网络访问。
    if (_socketpair_code is not None and sys._getframe(1).f_code is _socketpair_code
            and isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}):
        return _socket_connect(sock, address)
    return deny_network()


@event.listens_for(Engine, "do_connect")
def sqlite_only(dialect, _record, _args, _kwargs):
    if dialect.name != "sqlite":
        raise RuntimeError("PR8 离线测试只允许合成 SQLite")


def main():
    if not sys.argv[1:]:
        raise SystemExit("请显式列出 PR8 离线测试文件，不默认运行全仓或 PG 集成测试")
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.update(DATABASE_URL="", REMOTE_DB_URL="", MEDQC_ALLOW_REAL_LLM="0", MEDQC_PG_RACE_NONPROD_DB="",
                      JWT_SECRET="synthetic-pr8-offline-test-secret-not-for-use")
    with patch.object(dotenv, "load_dotenv", return_value=False), \
            patch.object(DotEnvSettingsSource, "_read_env_files", return_value={}), \
            patch.object(socket.socket, "connect", guarded_connect), \
            patch.object(socket, "create_connection", deny_network):
        from app.database import connection

        engine = create_engine("sqlite://")
        # 旧 persistence 模块要求导入时存在会话工厂；仍只绑定无表的合成内存库。
        connection.SessionLocal = sessionmaker(bind=engine)
        try:
            return pytest.main(["--noconftest", "-q", "--tb=short", "-o", "addopts=", *sys.argv[1:]])
        finally:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
