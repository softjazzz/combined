import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import http from "node:http";

const distRoot = process.argv[2];
if (!distRoot) {
  console.error("[serve_frontend] usage: node serve_frontend.mjs <dist_root>");
  process.exit(1);
}

const rootDir = resolve(distRoot);
const host = process.env.FRONTEND_HOST || "0.0.0.0";
const port = Number(process.env.FRONTEND_PORT || "3000");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".txt": "text/plain; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function sendFile(res, filePath) {
  const ext = extname(filePath).toLowerCase();
  const contentType = contentTypes[ext] || "application/octet-stream";
  res.statusCode = 200;
  res.setHeader("Content-Type", contentType);
  if (ext === ".html") {
    res.setHeader("Cache-Control", "no-cache");
  } else {
    res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
  }
  createReadStream(filePath).pipe(res);
}

function getFilePath(urlPath) {
  const safePath = normalize(decodeURIComponent(urlPath)).replace(/^(\.\.(\/|\\|$))+/, "");
  const candidate = resolve(join(rootDir, safePath));
  if (!candidate.startsWith(rootDir)) {
    return null;
  }
  if (existsSync(candidate)) {
    if (statSync(candidate).isDirectory()) {
      const indexPath = join(candidate, "index.html");
      if (existsSync(indexPath)) {
        return indexPath;
      }
    } else {
      return candidate;
    }
  }
  return null;
}

const server = http.createServer((req, res) => {
  try {
    const rawUrl = req.url || "/";
    const pathOnly = rawUrl.split("?")[0] || "/";
    const filePath = getFilePath(pathOnly);

    if (filePath) {
      sendFile(res, filePath);
      return;
    }

    const indexPath = join(rootDir, "index.html");
    if (!existsSync(indexPath)) {
      res.statusCode = 500;
      res.end("dist artifact is incomplete");
      return;
    }

    res.statusCode = 200;
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.setHeader("Cache-Control", "no-cache");
    createReadStream(indexPath).pipe(res);
  } catch (error) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.end(`frontend server error: ${error instanceof Error ? error.message : "unknown"}`);
  }
});

server.listen(port, host, () => {
  console.log(`[serve_frontend] serving ${rootDir} at http://${host}:${port}`);
});
