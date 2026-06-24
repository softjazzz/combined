#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import process from "node:process";

function run(cmd, cmdArgs) {
  return spawnSync(cmd, cmdArgs, {
    stdio: "inherit",
    shell: false,
  });
}

function canRun(cmd, cmdArgs) {
  const result = spawnSync(cmd, cmdArgs, {
    stdio: "ignore",
    shell: false,
  });
  return !result.error && (result.status ?? 1) === 0;
}

const scriptPath = "backend/scripts/check_sheet2_exact_review_regression.py";
const tried = [];

if (process.platform === "win32" && canRun("py", ["-3.10", "--version"])) {
  tried.push(["py", ["-3.10", scriptPath]]);
}
if (canRun("python", ["--version"])) {
  tried.push(["python", [scriptPath]]);
}

let lastError = null;
let lastStatus = 1;
for (const [cmd, cmdArgs] of tried) {
  const result = run(cmd, cmdArgs);
  if (!result.error && (result.status ?? 1) === 0) {
    process.exit(0);
  }
  if (!result.error) {
    lastStatus = result.status ?? 1;
    continue;
  }
  lastError = result.error;
}

if (!tried.length || lastError) {
  console.error(
    `[sheet2-exact-review-regression] 执行失败：找不到可用 Python 解释器。最后错误：${String(lastError)}`
  );
  process.exit(2);
}
process.exit(lastStatus);
