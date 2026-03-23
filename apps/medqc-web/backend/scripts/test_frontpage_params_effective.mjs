#!/usr/bin/env node
/**
 * 首页抽取参数生效性验证脚本
 *
 * 用法：
 *   node backend/scripts/test_frontpage_params_effective.mjs
 *   node backend/scripts/test_frontpage_params_effective.mjs --base-url http://127.0.0.1:8001
 *   node backend/scripts/test_frontpage_params_effective.mjs --timeout 90000
 *
 * 说明：
 * - 脚本会临时修改 /api/v1/frontpage/settings，然后自动恢复原配置
 * - 重点验证“后台可配置参数”是否真正影响接口行为
 */

import process from "node:process";

function parseArgs(argv) {
  const args = {
    baseUrl: "http://127.0.0.1:8001",
    timeoutMs: 120000,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const k = argv[i];
    const v = argv[i + 1];
    if (k === "--base-url" && v) {
      args.baseUrl = v.replace(/\/+$/, "");
      i += 1;
    } else if (k === "--timeout" && v) {
      args.timeoutMs = Number(v);
      i += 1;
    }
  }
  return args;
}

async function httpJson(url, options = {}) {
  const res = await fetch(url, options);
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { raw: text };
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} -> ${JSON.stringify(body)}`);
  }
  return body;
}

function pickSettingsBody(respBody) {
  if (respBody?.settings) return respBody.settings;
  if (respBody?.data?.settings) return respBody.data.settings;
  return respBody ?? {};
}

function pickWorkstationRecords(respBody) {
  if (Array.isArray(respBody?.records)) return respBody.records;
  if (Array.isArray(respBody?.data?.records)) return respBody.data.records;
  return [];
}

async function getFrontpageSettings(baseUrl) {
  const body = await httpJson(`${baseUrl}/api/v1/frontpage/settings`);
  return pickSettingsBody(body);
}

async function putFrontpageSettings(baseUrl, patch) {
  const body = await httpJson(`${baseUrl}/api/v1/frontpage/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return pickSettingsBody(body);
}

async function getWorkstationRecords(baseUrl) {
  const candidates = [
    `${baseUrl}/api/medical-records/workstation?page=1&page_size=50`,
    `${baseUrl}/api/v1/medical-records/workstation?page=1&page_size=50`,
  ];
  let lastErr = null;
  for (const url of candidates) {
    try {
      const body = await httpJson(url);
      return pickWorkstationRecords(body);
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr || new Error("workstation 接口不可用");
}

async function readSseEvents(baseUrl, payload, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort("timeout"), timeoutMs);

  try {
    const res = await fetch(`${baseUrl}/api/v1/frontpage/auto-generate-draft-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    if (!res.ok || !res.body) {
      throw new Error(`SSE请求失败: ${res.status} ${res.statusText}`);
    }

    const decoder = new TextDecoder("utf-8");
    const reader = res.body.getReader();
    let buffer = "";
    const events = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const lines = block.split("\n").map((x) => x.trimEnd());
        let eventName = "";
        let dataText = "";
        for (const line of lines) {
          if (!line || line.startsWith(":")) continue;
          if (line.startsWith("event:")) {
            eventName = line.slice("event:".length).trim();
          } else if (line.startsWith("data:")) {
            dataText += line.slice("data:".length).trim();
          }
        }
        if (!eventName) continue;
        let data = null;
        try {
          data = dataText ? JSON.parse(dataText) : null;
        } catch {
          data = { raw: dataText };
        }
        events.push({ event: eventName, data });
        if (eventName === "done" || eventName === "error") {
          try {
            await reader.cancel();
          } catch {
            // ignore
          }
          return events;
        }
      }
    }
    return events;
  } finally {
    clearTimeout(timer);
  }
}

function resultLine(name, status, detail) {
  const mark = status === "PASS" ? "✅" : status === "WARN" ? "⚠️" : "❌";
  return `${mark} [${status}] ${name} - ${detail}`;
}

function staticUsageReport() {
  // 这是基于当前代码的静态结论，用于解释“为什么某些参数改了看不出效果”
  return [
    {
      param: "stream_progress_enabled",
      expected: "影响 /auto-generate-draft-stream 是否输出 update 事件",
      runtimeHook: "backend/app/routers/frontpage.py:291",
    },
    {
      param: "allow_force_llm_regenerate",
      expected: "影响 force_llm 参数是否被接受",
      runtimeHook: "backend/app/services/frontpage_settings.py:91-99 + routers/frontpage.py:243-251",
    },
    {
      param: "llm_backfill_enabled",
      expected: "与 allow_force_llm_regenerate 共同控制 force_llm",
      runtimeHook: "backend/app/services/frontpage_settings.py:95",
    },
    {
      param: "include_demo_records / auto_hide_demo_when_real_data / demo_hide_threshold",
      expected: "影响工作台接口是否展示 demo 病历",
      runtimeHook: "backend/app/routers/medical_records.py:417",
    },
    {
      param: "sql_prefill_enabled",
      expected: "理论上应控制 SQL 预填层",
      runtimeHook: "当前未发现被消费（仅定义于 settings schema）",
    },
    {
      param: "default_preview_tab",
      expected: "前端默认展示 tab",
      runtimeHook: "后端未消费（仅透传配置）",
    },
  ];
}

async function main() {
  const { baseUrl, timeoutMs } = parseArgs(process.argv);
  console.log(`\n=== 首页抽取参数生效性验证 ===`);
  console.log(`baseUrl: ${baseUrl}`);
  console.log(`timeout: ${timeoutMs}ms\n`);

  let original = null;
  const logs = [];

  const sampleMedicalText = [
    "主诉：反复胸闷3年，加重伴胸痛1周",
    "初步诊断：",
    "1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛",
    "2. 高血压病3级 极高危",
    "3. 2型糖尿病",
    "诊疗计划：拟行冠状动脉造影",
  ].join("\n");

  try {
    original = await getFrontpageSettings(baseUrl);
    console.log("当前设置：", original);

    // 1) stream_progress_enabled 生效性
    await putFrontpageSettings(baseUrl, { stream_progress_enabled: true });
    const eventsOn = await readSseEvents(
      baseUrl,
      { medical_text: sampleMedicalText, force_llm: false },
      timeoutMs,
    );
    const updateOn = eventsOn.filter((e) => e.event === "update").length;
    const doneOn = eventsOn.filter((e) => e.event === "done").length;

    await putFrontpageSettings(baseUrl, { stream_progress_enabled: false });
    const eventsOff = await readSseEvents(
      baseUrl,
      { medical_text: sampleMedicalText, force_llm: false },
      timeoutMs,
    );
    const updateOff = eventsOff.filter((e) => e.event === "update").length;
    const doneOff = eventsOff.filter((e) => e.event === "done").length;

    if (updateOn > 0 && updateOff === 0 && doneOn > 0 && doneOff > 0) {
      logs.push(resultLine("stream_progress_enabled", "PASS", `update事件: 开=${updateOn}, 关=${updateOff}`));
    } else {
      logs.push(resultLine("stream_progress_enabled", "WARN", `结果不典型，开=${updateOn}, 关=${updateOff}, done开关=${doneOn}/${doneOff}`));
    }

    // 2) demo 相关参数生效性
    await putFrontpageSettings(baseUrl, {
      include_demo_records: true,
      auto_hide_demo_when_real_data: false,
      demo_hide_threshold: 99999,
    });
    const recordsWithDemo = await getWorkstationRecords(baseUrl);

    await putFrontpageSettings(baseUrl, {
      include_demo_records: false,
    });
    const recordsWithoutDemo = await getWorkstationRecords(baseUrl);

    const nWithDemo = recordsWithDemo.length;
    const nWithoutDemo = recordsWithoutDemo.length;
    if (nWithDemo >= nWithoutDemo) {
      const detail = `workstation记录数: 开demo=${nWithDemo}, 关demo=${nWithoutDemo}`;
      if (nWithDemo > nWithoutDemo) logs.push(resultLine("include_demo_records", "PASS", detail));
      else logs.push(resultLine("include_demo_records", "WARN", `${detail}（当前数据下差异不明显）`));
    } else {
      logs.push(resultLine("include_demo_records", "FAIL", `异常：开demo(${nWithDemo}) < 关demo(${nWithoutDemo})`));
    }

    // 3) force_llm 控制参数只做静态+配置写读验证（运行态依赖 LLM/SQL 场景）
    const afterSet = await putFrontpageSettings(baseUrl, {
      allow_force_llm_regenerate: false,
      llm_backfill_enabled: false,
    });
    const forceFlagsOk =
      afterSet.allow_force_llm_regenerate === false && afterSet.llm_backfill_enabled === false;
    logs.push(
      resultLine(
        "allow_force_llm_regenerate + llm_backfill_enabled",
        forceFlagsOk ? "PASS" : "FAIL",
        forceFlagsOk
          ? "配置写读正常；运行时在 resolve_force_llm 中参与判定（见静态报告）"
          : "配置回写值异常",
      ),
    );

    // 4) sql_prefill_enabled / default_preview_tab 检查
    const usage = staticUsageReport();
    const sqlPrefill = usage.find((x) => x.param === "sql_prefill_enabled");
    const defaultTab = usage.find((x) => x.param === "default_preview_tab");
    logs.push(resultLine("sql_prefill_enabled", "WARN", sqlPrefill.runtimeHook));
    logs.push(resultLine("default_preview_tab", "WARN", defaultTab.runtimeHook));

    console.log("\n=== 验证结果 ===");
    logs.forEach((x) => console.log(x));

    console.log("\n=== 参数静态挂钩说明 ===");
    usage.forEach((u) => {
      console.log(`- ${u.param}`);
      console.log(`  预期: ${u.expected}`);
      console.log(`  挂钩: ${u.runtimeHook}`);
    });
  } catch (err) {
    console.error("\n脚本执行失败：", err?.message || err);
    process.exitCode = 1;
  } finally {
    if (original) {
      try {
        await putFrontpageSettings(baseUrl, original);
        console.log("\n已恢复原始 frontpage settings。");
      } catch (restoreErr) {
        console.error("\n恢复原配置失败，请手动检查 /api/v1/frontpage/settings：", restoreErr?.message || restoreErr);
        process.exitCode = 1;
      }
    }
  }
}

main();
