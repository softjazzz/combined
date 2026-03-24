#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


class SpaHandler(SimpleHTTPRequestHandler):
    """静态资源正常返回，其他路径回退 index.html。"""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        rel = unquote(parsed.path).lstrip("/")
        return str(Path(self.directory, rel))

    def do_GET(self):
        target = Path(self.translate_path(self.path))
        if target.is_file():
            return super().do_GET()
        # SPA 回退到 index.html
        self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        target = Path(self.translate_path(self.path))
        if target.is_file():
            return super().do_HEAD()
        self.path = "/index.html"
        return super().do_HEAD()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve dist as SPA with history fallback")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--dir", default="dist")
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    if not root.exists():
        raise SystemExit(f"dist directory not found: {root}")
    if not (root / "index.html").exists():
        raise SystemExit(f"index.html not found under: {root}")

    server = ThreadingHTTPServer(
        (args.host, args.port),
        lambda *a, **kw: SpaHandler(*a, directory=str(root), **kw),
    )
    print(f"[serve_dist_spa.py] http://{args.host}:{args.port}  dir={root}")
    server.serve_forever()


if __name__ == "__main__":
    main()

