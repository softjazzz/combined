"""离线测量原生 DSH trace；只输出体积/调用元数据，不输出患者原文。"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def analyze(results_path: Path, trace_root: Path):
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    wanted = {row["session_id"] for row in rows}
    aggregate = defaultdict(lambda: {"calls": 0, "model_bytes": 0, "presentation_bytes": 0, "fields": defaultdict(int)})
    requests = []
    for path in trace_root.rglob("*.jsonl"):
        with path.open(encoding="utf-8") as stream:
            header = json.loads(next(stream))
            if header.get("id") not in wanted:
                continue
            events = [json.loads(line) for line in stream if line.strip()]
        surface = []
        calls = {}
        active_turn = 0
        for event in events:
            kind, data = event["type"], event["data"]
            if kind == "turn/start":
                active_turn = data["turn"]
            if kind == "tool/call":
                calls[data["callId"]] = data["name"]
            if kind in {"assistant/message", "assistant/attempt"}:
                # 同一有序 surface 中的既往文本会随每次模型调用重放；单位字节，不冒充 Token。
                total = prior = tool = 0
                for _, turn, message in surface:
                    for block in message.get("content", []):
                        contents = block.get("content", []) if block["type"] == "tool-result" else [block]
                        for content in contents:
                            amount = len(content.get("text", "").encode("utf-8"))
                            total += amount
                            if turn < data["turn"]:
                                prior += amount
                            if block["type"] == "tool-result":
                                tool += amount
                requests.append({"session_id": header["id"], "turn": data["turn"], "step": data["step"], "text_bytes": total, "prior_turn_text_bytes": prior, "tool_text_bytes": tool, "usage": data.get("usage")})
            message = data if kind == "user/message" else data.get("message")
            if kind == "tool/result":
                for block in message["content"]:
                    if block["type"] != "tool-result" or block.get("isError"):
                        continue
                    name = calls[block["toolCallId"]]
                    metric = aggregate[name]
                    metric["calls"] += 1
                    metric["presentation_bytes"] += size(data.get("meta", {}))
                    for content in block.get("content", []):
                        if content.get("type") != "text":
                            continue
                        metric["model_bytes"] += len(content["text"].encode("utf-8"))
                        value = json.loads(content["text"])
                        for key, item in value.items():
                            metric["fields"][key] += size(item)
                        for reference in value.get("references", []):
                            for key, item in reference.items():
                                metric["fields"]["references." + key] += size(item)
            operation = event.get("surfaceOp")
            if operation and message:
                if isinstance(operation, dict) and operation["op"] == "replace":
                    first = next(i for i, node in enumerate(surface) if node[0] == operation["startSeq"])
                    last = next(i for i, node in enumerate(surface) if node[0] == operation["endSeq"])
                    surface[first:last + 1] = [(event["seq"], data.get("turn", active_turn), message)]
                else:
                    surface.append((event["seq"], data.get("turn", active_turn), message))
    return {"tools": dict(aggregate), "requests": requests, "request_totals": {key: sum(row[key] for row in requests) for key in ("text_bytes", "prior_turn_text_bytes", "tool_text_bytes")}, "unit_note": "UTF-8文本字节；不含schema及协议封装，不等于供应商Token"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.results, args.trace_root)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"tools": report["tools"], "request_totals": report["request_totals"]}, ensure_ascii=True))
