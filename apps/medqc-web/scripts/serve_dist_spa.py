#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import http.client
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
        if self._maybe_proxy():
            return
        target = Path(self.translate_path(self.path))
        if target.is_file():
            return super().do_GET()
        # SPA 回退到 index.html
        self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        if self._maybe_proxy():
            return
        target = Path(self.translate_path(self.path))
        if target.is_file():
            return super().do_HEAD()
        self.path = "/index.html"
        return super().do_HEAD()

    def do_POST(self):
        if self._maybe_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self):
        if self._maybe_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_PATCH(self):
        if self._maybe_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self):
        if self._maybe_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_OPTIONS(self):
        if self._maybe_proxy():
            return
        self.send_response(204)
        self.end_headers()

    def _maybe_proxy(self) -> bool:
        api_target = getattr(self.server, "api_target", None)
        if not api_target:
            return False
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return False
        self._proxy_request(api_target)
        return True

    def _proxy_request(self, api_target: str) -> None:
        target = urlparse(api_target)
        path = self.path
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else None
        connection_cls = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        conn = connection_cls(target.hostname, target.port or (443 if target.scheme == "https" else 80), timeout=60)

        forwarded_headers = {}
        for key, value in self.headers.items():
            lower = key.lower()
            if lower in {"host", "connection", "content-length"}:
                continue
            forwarded_headers[key] = value
        forwarded_headers["Host"] = target.netloc

        try:
            conn.request(self.command, path, body=body, headers=forwarded_headers)
            response = conn.getresponse()
            response_body = response.read()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                lower = key.lower()
                if lower in {"transfer-encoding", "connection", "content-length", "server", "date"}:
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response_body)
        finally:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve dist as SPA with history fallback")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--dir", default="dist")
    parser.add_argument("--api-target", default="", help="Optional backend target for /api reverse proxy")
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
    server.api_target = args.api_target.strip().rstrip("/")
    print(
        f"[serve_dist_spa.py] http://{args.host}:{args.port}  dir={root}"
        + (f"  api_target={server.api_target}" if server.api_target else "")
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
