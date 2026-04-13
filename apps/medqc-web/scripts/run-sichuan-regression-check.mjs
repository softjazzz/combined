#!/usr/bin/env node
/**
 * 四川执行链回归检查包装脚本。
 *
 * 默认策略（不阻塞开发）：
 * - 未设置 RUN_SICHUAN_REGRESSION=1 时直接跳过并返回 0。
 * - 设置后执行 compare-sichuan-orchestrator-modes.py。
 *
 * 严格模式：
 * - 传入 --required 或设置 RUN_SICHUAN_REGRESSION_REQUIRED=1。
 * - 严格模式下，未开启回归或执行失败都会返回非 0。
 */

import { spawnSync } from "node:child_process";
import process from "node:process";

const args = new Set(process.argv.slice(2));
const required =
  args.has("--required") || process.env.RUN_SICHUAN_REGRESSION_REQUIRED === "1";
const enabled = process.env.RUN_SICHUAN_REGRESSION === "1";

function run(cmd, cmdArgs) {
  return spawnSync(cmd, cmdArgs, {
    stdio: "inherit",
    shell: false,
  });
}

if (!enabled) {
  const message =
    "[sichuan-regression] 跳过：未设置 RUN_SICHUAN_REGRESSION=1（默认非阻塞）";
  if (required) {
    console.error(`${message}；当前为严格模式，返回失败。`);
    process.exit(2);
  }
  console.log(message);
  process.exit(0);
}

const scriptPath = "scripts/compare-sichuan-orchestrator-modes.py";
const tried = [];

if (process.platform === "win32") {
  tried.push(["py", ["-3.10", scriptPath]]);
}
tried.push(["python", [scriptPath]]);

let lastResult = null;
for (const [cmd, cmdArgs] of tried) {
  const result = run(cmd, cmdArgs);
  if (!result.error) {
    process.exit(result.status ?? 1);
  }
  lastResult = result.error;
}

console.error(
  `[sichuan-regression] 执行失败：找不到可用 Python 解释器。最后错误：${String(lastResult)}`
);
process.exit(2);

