import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const distDir = path.join(root, "dist");
const port = Number(process.env.PORT || 3000);
const host = process.env.HOST || "127.0.0.1";

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function send(res, code, data, contentType = "text/plain; charset=utf-8") {
  res.writeHead(code, { "Content-Type": contentType, "Cache-Control": "no-cache" });
  res.end(data);
}

function safeResolve(base, reqPath) {
  const p = path.normalize(path.join(base, reqPath));
  return p.startsWith(base) ? p : null;
}

if (!fs.existsSync(distDir)) {
  console.error(`[serve-dist-spa] dist 不存在: ${distDir}`);
  console.error("[serve-dist-spa] 需要先有可用 dist 产物。");
  process.exit(1);
}

const server = http.createServer((req, res) => {
  const parsed = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
  let reqPath = decodeURIComponent(parsed.pathname || "/");
  if (reqPath === "/") reqPath = "/index.html";

  const abs = safeResolve(distDir, reqPath.replace(/^\/+/, ""));
  if (!abs) {
    send(res, 403, "Forbidden");
    return;
  }

  fs.stat(abs, (err, stat) => {
    const target = !err && stat.isFile() ? abs : path.join(distDir, "index.html");
    fs.readFile(target, (readErr, buf) => {
      if (readErr) {
        send(res, 500, `Read failed: ${readErr.message}`);
        return;
      }
      const ext = path.extname(target).toLowerCase();
      send(res, 200, buf, mime[ext] || "application/octet-stream");
    });
  });
});

server.listen(port, host, () => {
  console.log(`[serve-dist-spa] http://${host}:${port}`);
  console.log(`[serve-dist-spa] dist=${distDir}`);
});

