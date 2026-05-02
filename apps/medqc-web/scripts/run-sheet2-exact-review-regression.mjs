#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import process from "node:process";

function run(cmd, cmdArgs) {
  return spawnSync(cmd, cmdArgs, {
    stdio: "inherit",
    shell: false,
  });
}

const scriptPath = "backend/scripts/check_sheet2_exact_review_regression.py";
const tried = [];

if (process.platform === "win32") {
  tried.push(["py", ["-3.10", scriptPath]]);
}
tried.push(["python", [scriptPath]]);

let lastError = null;
for (const [cmd, cmdArgs] of tried) {
  const result = run(cmd, cmdArgs);
  if (!result.error) {
    process.exit(result.status ?? 1);
  }
  lastError = result.error;
}

console.error(
  `[sheet2-exact-review-regression] 执行失败：找不到可用 Python 解释器。最后错误：${String(lastError)}`
);
process.exit(2);
