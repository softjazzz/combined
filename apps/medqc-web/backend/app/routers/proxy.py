from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from ..core.response import success_response, paginated_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..core.http import safe_post_json
from ..core.settings import get_settings

router = APIRouter(prefix="/api/llm", tags=["llm-proxy"])


@router.post("/parse-text")
async def llm_parse_text_proxy(
    request: Request,payload: Dict[str, Any]):
    # Minimal safe placeholder: validate input shape and refuse if missing
    api_config = payload.get("apiConfig") or {}
    request_body = payload.get("requestBody") or {}

    api_endpoint = (api_config.get("apiEndpoint") or "").strip()
    api_key = api_config.get("apiKey") or ""

    if not api_endpoint or not api_key:
        return JSONResponse(status_code=StatusCode.BAD_REQUEST, content={
            'error': 'Missing apiEndpoint or apiKey',
            'apiEndpoint': bool(api_endpoint),
            'apiKeyProvided': bool(api_key)
        })

    # 兼容性修正：DashScope/OpenAI 兼容端点若仅到 /v1，自动补全 /chat/completions
    endpoint_l = api_endpoint.rstrip('/').lower()
    if ("dashscope.aliyuncs.com" in endpoint_l or "openai.com" in endpoint_l) and endpoint_l.endswith("/v1"):
        api_endpoint = api_endpoint.rstrip('/') + '/chat/completions'

    # 阿里云部分模型需要 enable_thinking=false（非流式）等兼容项
    model_name = request_body.get('model', '')
    if 'dashscope.aliyuncs.com' in endpoint_l:
        thinking_required_models = [
            'qwen2.5-14b-instruct',
            'qwen2.5-32b-instruct',
            'qwen3-14b',
            'qwen3-30b-a3b-instruct-2507'
        ]
        if model_name in thinking_required_models and not request_body.get('stream', False):
            request_body['enable_thinking'] = False
        # 某些 qwen 模型对 response_format=json_object 支持不稳定，移除以提高兼容性
        rf = request_body.get('response_format')
        if isinstance(rf, dict) and rf.get('type') == 'json_object' and (model_name.startswith('qwen2.5') or model_name.startswith('qwen3')):
            request_body.pop('response_format', None)

    settings = get_settings()
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        result = await safe_post_json(api_endpoint, headers, request_body, timeout_seconds=60)
        # 若上游返回错误，透传其状态码与消息
        if isinstance(result, dict) and result.get("__error__"):
            return JSONResponse(status_code=int(result.get("__status__", 502)), content=result.get("body") or {"error": "UpstreamError"})
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": "ProxyError", "message": str(e)})
