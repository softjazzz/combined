"""正式入口合成测试专属隔离：导入应用前阻断配置文件和外部访问。"""
from pathlib import Path
import builtins
import io
import os
import socket
import sys
from unittest.mock import patch


def install_offline_guard():
    import dotenv
    import dotenv.main
    from sqlalchemy.engine import Engine

    # 只提供固定合成配置；不读取或打印既有数据库配置。
    os.environ["DATABASE_URL"] = "postgresql+psycopg2://synthetic:synthetic@offline.invalid/synthetic"
    os.environ["JWT_SECRET"] = "scope-six-synthetic-jwt-secret"
    guards = []

    def keep(target, replacement):
        guard = patch(target, replacement)
        guard.start()
        guards.append(guard)

    keep("dotenv.load_dotenv", lambda *args, **kwargs: False)
    keep("dotenv.main.load_dotenv", lambda *args, **kwargs: False)
    keep("dotenv.dotenv_values", lambda *args, **kwargs: {})
    keep("dotenv.main.dotenv_values", lambda *args, **kwargs: {})

    def guarded_open(original):
        def opened(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                name = Path(os.fsdecode(file)).name.lower()
                if name == ".env" or name.startswith(".env."):
                    raise AssertionError("SCOPE-06 禁止读取环境配置文件")
            return original(file, *args, **kwargs)
        return opened

    keep("builtins.open", guarded_open(builtins.open))
    keep("io.open", guarded_open(io.open))
    original_raw_connection = Engine.raw_connection

    def sqlite_only(engine):
        if engine.dialect.name != "sqlite":
            raise AssertionError("SCOPE-06 仅允许合成 SQLite 数据库")
        return original_raw_connection(engine)

    keep("sqlalchemy.engine.Engine.raw_connection", sqlite_only)
    # 只允许标准库 socket.py/socketpair 构造 asyncio 内部唤醒管道。
    socket_module_path = Path(socket.__file__).resolve()

    def stdlib_socketpair_call():
        frame = sys._getframe(1)
        while frame is not None:
            if (
                frame.f_code.co_name == "socketpair"
                and Path(frame.f_code.co_filename).resolve() == socket_module_path
            ):
                return True
            frame = frame.f_back
        return False

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def local_connect(original):
        def connected(sock, address):
            if (
                sock.family in (socket.AF_INET, socket.AF_INET6)
                and not stdlib_socketpair_call()
            ):
                raise AssertionError("SCOPE-06 禁止网络连接")
            return original(sock, address)
        return connected

    keep("socket.socket.connect", local_connect(original_connect))
    keep("socket.socket.connect_ex", local_connect(original_connect_ex))
    import psycopg2

    def no_pg(*args, **kwargs):
        raise AssertionError("SCOPE-06 禁止 PostgreSQL 连接")

    keep("psycopg2.connect", no_pg)
    return guards
