from typing import Dict, Any, List, Optional, Tuple
import time
import logging

from ..core.settings import get_settings
from ..core.http import safe_post_json
from ..core.supabase_client import get_supabase
from .unified_rule_engine import UnifiedRuleEngine
from .llm_config_loader import LLMConfigLoader

logger = logging.getLogger(__name__)


class SichuanQCLLMClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化 LLM 客户端

        Args:
            config: 配置字典，如果为 None 则从 .env 文件加载
                   配置字典应包含：
                   - api_endpoint: API 端点
                   - api_key: API 密钥
                   - model: 模型代码
                   - timeout_seconds: 超时时间
        """
        if config:
            # 使用传入的配置
            self.api_endpoint: Optional[str] = config.get("api_endpoint")
            self.api_key: Optional[str] = config.get("api_key")
            self.model: str = config.get("model", "qwen2.5-14b-instruct")
            self.timeout_seconds: int = config.get("timeout_seconds", 120)
            self.config_source = config.get("source", "unknown")

            # Load advanced LLM parameters from custom_parameters
            custom_params = config.get("custom_parameters", {})
            self.temperature: float = custom_params.get("temperature", 0.2)
            self.top_p: float = custom_params.get("top_p", 0.9)
            self.max_tokens: int = custom_params.get("max_tokens", 4000)

            logger.info(f"✅ SichuanQCLLMClient 使用传入配置初始化: model={self.model}, source={self.config_source}, temperature={self.temperature}, top_p={self.top_p}, max_tokens={self.max_tokens}")
        else:
            # 回退到 .env 文件配置
            s = get_settings()
            self.api_endpoint: Optional[str] = str(s.SICHUAN_API_ENDPOINT) if s.SICHUAN_API_ENDPOINT else None
            self.api_key: Optional[str] = s.SICHUAN_API_KEY
            self.model: str = s.SICHUAN_MODEL
            self.timeout_seconds: int = s.SICHUAN_TIMEOUT_SECONDS
            self.config_source = "env"

            # Default advanced parameters when using .env
            self.temperature: float = 0.2
            self.top_p: float = 0.9
            self.max_tokens: int = 4000

            logger.info(f"✅ SichuanQCLLMClient 使用 .env 配置初始化: model={self.model}, temperature={self.temperature}")

        # Stats
        self.call_count = 0
        self.total_tokens = 0
        self.total_api_time = 0.0
        self.success_count = 0
        self.error_count = 0

    async def generate(self, prompt: str) -> Dict[str, Any]:
        self.call_count += 1
        api_start = time.time()

        if not (self.api_endpoint and self.api_key):
            # Mock result when not configured
            api_time = time.time() - api_start
            self.success_count += 1
            return {
                "choices": [{"message": {"content": f"[MOCK RESULT] 分析完成: {prompt[:60]}..."}}],
                "usage": {"total_tokens": 0},
                "_mock": True,
                "_api_time": api_time,
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,  # 使用配置的 temperature
            "top_p": self.top_p,              # 使用配置的 top_p
            "max_tokens": self.max_tokens,    # 使用配置的 max_tokens
            "stream": False,
            "enable_thinking": False,  # Qwen3 系列模型需要此参数
        }

        try:
            result = await safe_post_json(
                url=f"{self.api_endpoint}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
            api_time = time.time() - api_start
            self.total_api_time += api_time
            self.success_count += 1
            usage = result.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)
            result["_api_time"] = api_time
            return result
        except Exception:
            api_time = time.time() - api_start
            self.total_api_time += api_time
            self.error_count += 1
            raise

    def stats(self) -> Dict[str, Any]:
        return {
            "total_calls": self.call_count,
            "success_calls": self.success_count,
            "error_calls": self.error_count,
            "success_rate": (self.success_count / self.call_count * 100) if self.call_count else 0.0,
            "total_tokens": self.total_tokens,
            "total_api_time": self.total_api_time,
            "avg_api_time": (self.total_api_time / self.call_count) if self.call_count else 0.0,
        }


class SichuanQCService:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化四川质控服务

        Args:
            config: LLM 配置字典，如果为 None 则从 .env 文件加载
        """
        self.client = SichuanQCLLMClient(config)
        self._rules_cache: Optional[List[Dict[str, Any]]] = None
        self.rule_engine = UnifiedRuleEngine(self.client.generate)
        # 英文到中文文书类型映射（兼容多种同义英文编码）
        self.doc_type_mapping = {
            # 基础映射
            "admission_record": "入院记录",
            "progress_note": "病程记录",
            "operation_record": "手术记录",
            "discharge_record": "出院记录",
            "consent_form": "知情同意书",
            "examination_report": "检查报告",
            "medical_order": "医嘱",
            # 同义/变体编码（JSON 中存在的别名）
            "course_record": "病程记录",            # 病程记录别名
            "consultation_record": "病程记录",      # 会诊记录归入病程
            "case_discussion": "病程记录",          # 病例讨论归入病程
            "discharge_summary": "出院记录",        # 出院小结归入出院
            "lab_report": "检查报告",               # 检验报告归入检查报告
            "anesthesia_record": "手术记录",        # 麻醉记录归入手术相关
            "transfusion_record": "病程记录",       # 输血记录归入病程
            "informed_consent": "知情同意书",       # 同意书归类
        }
        # 初始化截断配置
        from ..core.settings import get_settings
        settings = get_settings()
        self.enable_truncate = settings.SICHUAN_ENABLE_TRUNCATE
        self.max_content_length = settings.SICHUAN_MAX_CONTENT_LENGTH

    async def reload_config(self, config_name: str = "default", user_id: Optional[str] = None) -> bool:
        """
        重新加载 LLM 配置

        Args:
            config_name: 配置名称，默认为 "default"
            user_id: 用户 ID，如果为 None 则加载全局配置

        Returns:
            是否成功重新加载配置
        """
        return await LLMConfigLoader.reload_config_for_service(self, config_name, user_id)
        # 加载截断配置
        from ..core.settings import get_settings
        settings = get_settings()
        self.enable_truncate = settings.SICHUAN_ENABLE_TRUNCATE
        self.max_content_length = settings.SICHUAN_MAX_CONTENT_LENGTH

    def _load_rules_from_json(self) -> List[Dict[str, Any]]:
        """
        从 JSON 文件加载四川省规则（带缓存）
        """
        if self._rules_cache is not None:
            return self._rules_cache

        import json
        import os

        json_path = os.path.join(
            os.path.dirname(__file__),
            "..", "data", "sichuan_rules_146.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                rules = json.load(f)

            # 转换 applicable_documents 从英文到中文
            for rule in rules:
                applicable_docs = rule.get("applicable_documents", [])
                if applicable_docs:
                    rule["applicable_documents"] = [
                        self.doc_type_mapping.get(doc, doc)
                        for doc in applicable_docs
                    ]

            self._rules_cache = rules
            logger.info(f"从 JSON 文件加载了 {len(rules)} 条四川省规则")
            return rules
        except Exception as e:
            logger.error(f"从 JSON 文件加载规则失败: {e}", exc_info=True)
            return []

    def _load_custom_rules_from_json(self) -> List[Dict[str, Any]]:
        """
        从 JSON 文件加载自定义规则（泸县33条规则）
        """
        import json
        import os

        json_path = os.path.join(
            os.path.dirname(__file__),
            "..", "data", "custom_rules_33.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                rules = json.load(f)

            # 转换 applicable_documents 从英文到中文
            for rule in rules:
                applicable_docs = rule.get("applicable_documents", [])
                if applicable_docs:
                    rule["applicable_documents"] = [
                        self.doc_type_mapping.get(doc, doc)
                        for doc in applicable_docs
                    ]

            logger.info(f"从 JSON 文件加载了 {len(rules)} 条自定义规则")
            return rules
        except Exception as e:
            logger.error(f"从 JSON 文件加载自定义规则失败: {e}", exc_info=True)
            return []

    async def _load_rules_from_db(self, document_type: str) -> List[Dict[str, Any]]:
        """
        从 JSON 文件或 Supabase 数据库加载适用于指定文书类型的质控规则。

        Args:
            document_type: 文书类型（如 "病程记录"、"入院记录" 等）

        Returns:
            适用规则列表。如果加载失败，返回空列表。

        规则筛选逻辑：
        1. 优先从 JSON 文件加载（包含完整的 applicable_documents 等字段）
        2. 如果 JSON 加载失败，回退到数据库
        3. 通用规则（applicable_documents 为空）会被包含
        4. 特定规则（applicable_documents 包含指定的 document_type）会被包含
        """
        # 优先从 JSON 文件加载
        try:
            all_rules = self._load_rules_from_json()
            if all_rules:
                # 筛选适用于当前文书类型的规则
                applicable_rules = []
                for rule in all_rules:
                    applicable_docs = rule.get("applicable_documents", [])
                    # 如果 applicable_documents 为空（通用规则）或包含当前文书类型
                    if not applicable_docs or document_type in applicable_docs:
                        applicable_rules.append(rule)

                logger.info(f"从 JSON 文件加载了 {len(applicable_rules)} 条适用于 '{document_type}' 的规则")
                return applicable_rules
        except Exception as e:
            logger.warning(f"从 JSON 文件加载规则失败，回退到数据库: {e}")

        # 回退到数据库
        try:
            supabase = get_supabase()
            if supabase is None:
                logger.warning("Supabase client not available, cannot load rules from database")
                return []

            # 尝试使用异步执行，如果不支持则使用同步执行
            async def _exec(query):
                try:
                    exec_async = getattr(query, "execute_async", None)
                    if callable(exec_async):
                        return await exec_async()
                except Exception:
                    pass
                return query.execute()

            # 使用数据库层面筛选（Migration 006 优化）
            try:
                # 方法 1: 使用 RPC 函数（推荐，最简洁）
                try:
                    resp = await _exec(
                        supabase.rpc(
                            'get_applicable_rules',
                            {'p_document_type': document_type, 'p_is_active': True}
                        )
                    )
                    applicable_rules = resp.data or []
                    logger.info(f"Loaded {len(applicable_rules)} rules for '{document_type}' using RPC function")
                    return applicable_rules
                except Exception as rpc_error:
                    logger.warning(f"RPC function not available, falling back to query: {rpc_error}")

                # 方法 2: 使用 Supabase 查询（回退方案）
                # 注意：这会匹配包含指定文书类型的规则，以及 applicable_documents 为空的通用规则
                resp = await _exec(
                    supabase.table("qc_rules")
                    .select("*")
                    .eq("is_active", True)
                    .or_(f"applicable_documents.cs.{{{document_type}}},applicable_documents.is.null,applicable_documents.eq.{{}}")
                    .limit(1000)
                )

                applicable_rules = resp.data or []
                logger.info(f"Loaded {len(applicable_rules)} rules for '{document_type}' using database query")
                return applicable_rules

            except Exception as db_filter_error:
                # 如果数据库层面筛选失败（可能是字段不存在或语法不支持），回退到应用层筛选
                logger.warning(f"Database-level filtering failed, falling back to application-level filtering: {db_filter_error}")

                # 加载所有激活的规则
                resp = await _exec(
                    supabase.table("qc_rules")
                    .select("*")
                    .eq("is_active", True)
                    .limit(1000)
                )

                all_rules = resp.data or []
                logger.info(f"Loaded {len(all_rules)} active rules from database")

                # 在应用层筛选适用于指定文书类型的规则
                applicable_rules = []
                for rule in all_rules:
                    # 优先从顶层 applicable_documents 字段读取（新字段）
                    applicable_docs = rule.get("applicable_documents", [])

                    # 如果顶层字段为空，尝试从 check_logic JSONB 字段读取（向后兼容）
                    if not applicable_docs:
                        check_logic = rule.get("check_logic", {})
                        if isinstance(check_logic, dict):
                            applicable_docs = check_logic.get("applicable_documents", [])

                    # 规范化为列表
                    if isinstance(applicable_docs, str):
                        applicable_docs = [d.strip() for d in applicable_docs.split(",") if d.strip()]
                    elif not isinstance(applicable_docs, list):
                        applicable_docs = []

                    # 筛选逻辑：
                    # 1. 如果 applicable_documents 为空，视为通用规则，包含该规则
                    # 2. 如果 applicable_documents 包含指定的 document_type，包含该规则
                    if not applicable_docs or document_type in applicable_docs:
                        applicable_rules.append(rule)

                logger.info(f"Found {len(applicable_rules)} rules applicable to document type '{document_type}' (application-level filtering)")
                return applicable_rules

        except Exception as e:
            logger.error(f"Failed to load rules from database: {e}", exc_info=True)
            return []

    def _smart_truncate(self, content: str, max_length: int = 4000) -> str:
        """
        智能截断病历内容，优先保留完整段落，避免切断句子。

        Args:
            content: 原始病历内容
            max_length: 最大字符长度

        Returns:
            截断后的内容，带有截断提示
        """
        if len(content) <= max_length:
            return content

        # 预留截断提示的空间（约80字符）
        reserve_space = 80
        effective_max = max_length - reserve_space

        # 截断到有效长度
        truncated = content[:effective_max]

        # 向前查找最近的段落分隔符（\n\n 或 \n）
        last_paragraph = truncated.rfind('\n\n')
        last_newline = truncated.rfind('\n')

        # 如果段落边界在合理范围内（90%以上），使用段落边界
        if last_paragraph > effective_max * 0.9:
            result = truncated[:last_paragraph]
        elif last_newline > effective_max * 0.8:
            result = truncated[:last_newline]
        else:
            # 如果没有合适的边界，查找最后一个句号
            last_period = truncated.rfind('。')
            if last_period > effective_max * 0.8:
                result = truncated[:last_period + 1]
            else:
                result = truncated

        # 添加截断标记
        total_chars = len(content)
        kept_chars = len(result)
        truncated_chars = total_chars - kept_chars

        result += f"\n\n[注：病历内容过长，已截断 {truncated_chars} 字符（保留前 {kept_chars}/{total_chars} 字符）]"

        logger.info(f"智能截断: 原始 {total_chars} 字符 → 保留 {kept_chars} 字符（{kept_chars/total_chars*100:.1f}%）")

        return result

    async def _evaluate_rules_with_engine(
        self,
        document_id: str,
        content: str,
        document_type: str,
        rules: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int, float]:
        """
        使用统一规则引擎对一组规则执行质控。

        Returns:
            (results, total_tokens, total_api_time)
        """
        results: List[Dict[str, Any]] = []
        total_tokens = 0
        total_api_time = 0.0

        for rule in rules:
            engine_result = await self.rule_engine.evaluate(
                rule,
                medical_record={
                    "id": document_id,
                    "content": content,
                    "document_type": document_type,
                },
            )
            results.append(engine_result)
            meta = engine_result.get("metadata", {}) or {}
            total_tokens += int(meta.get("tokens_used") or 0)
            total_api_time += float(meta.get("api_time") or 0.0)

        return results, total_tokens, total_api_time

    def _extract_check_points(self, custom_prompt: str) -> str:
        """
        从 custom_prompt 中提取检查要点

        Args:
            custom_prompt: 完整的自定义提示词

        Returns:
            提取的检查要点文本，如果没有则返回空字符串
        """
        if not custom_prompt:
            return ""

        # 查找【检查要点】部分
        start_marker = "【检查要点】"
        end_markers = ["【判定逻辑】", "【分析方法】", "【注意事项】", "【示例】"]

        start_idx = custom_prompt.find(start_marker)
        if start_idx == -1:
            return ""

        # 查找结束位置
        end_idx = len(custom_prompt)
        for marker in end_markers:
            idx = custom_prompt.find(marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx

        # 提取并清理
        check_points = custom_prompt[start_idx:end_idx].strip()
        return check_points

    def _extract_core_guidance(self, custom_prompt: str) -> str:
        """
        提取核心指导信息（检查要点 + 判定逻辑 + 分析方法）- 方案 C

        Args:
            custom_prompt: 完整的自定义提示词

        Returns:
            提取的核心指导信息
        """
        if not custom_prompt:
            return ""

        parts = []

        # 提取【检查要点】
        check_points = self._extract_check_points(custom_prompt)
        if check_points:
            parts.append(check_points)

        # 提取【判定逻辑】
        logic_start = custom_prompt.find("【判定逻辑】")
        if logic_start != -1:
            logic_end_markers = ["【分析方法】", "【注意事项】", "【示例】"]
            logic_end = len(custom_prompt)
            for marker in logic_end_markers:
                idx = custom_prompt.find(marker, logic_start)
                if idx != -1 and idx < logic_end:
                    logic_end = idx

            logic = custom_prompt[logic_start:logic_end].strip()
            if logic:
                parts.append(logic)

        return "\n\n".join(parts)

    def _extract_enhanced_guidance(self, custom_prompt: str, rule_id: str) -> str:
        """
        为复杂规则提取增强的指导信息（检查要点 + 判定逻辑）

        Args:
            custom_prompt: 完整的自定义提示词
            rule_id: 规则ID

        Returns:
            增强的指导信息
        """
        if not custom_prompt:
            return ""

        # 定义需要增强指导的复杂规则列表
        # 这些规则在测试中误判率较高，需要额外的判定逻辑
        complex_rules = {
            "LX-007",  # 入院记录缺辅助检查
            "LX-009",  # 入院记录缺初步诊断
            # 后续可以根据实际测试结果添加更多规则
        }

        # 如果不是复杂规则，只返回检查要点
        if rule_id not in complex_rules:
            return self._extract_check_points(custom_prompt)

        # 对于复杂规则，提取检查要点 + 判定逻辑
        parts = []

        # 提取【检查要点】
        check_points = self._extract_check_points(custom_prompt)
        if check_points:
            parts.append(check_points)

        # 提取【判定逻辑】
        logic_start = custom_prompt.find("【判定逻辑】")
        if logic_start != -1:
            logic_end_markers = ["【分析方法】", "【注意事项】", "【示例】"]
            logic_end = len(custom_prompt)
            for marker in logic_end_markers:
                idx = custom_prompt.find(marker, logic_start)
                if idx != -1 and idx < logic_end:
                    logic_end = idx

            logic = custom_prompt[logic_start:logic_end].strip()
            if logic:
                parts.append(logic)

        return "\n\n".join(parts)

    async def _build_prompt(
        self,
        rules: List[Dict[str, Any]],
        content: str,
        document_type: str,
        prompt_mode: str = "plan_a"
    ) -> str:
        """
        使用规则列表和病历内容构建质控分析 Prompt。

        Args:
            rules: 适用规则列表
            content: 病历内容
            document_type: 文书类型
            prompt_mode: 提示词优化方案
                - "current": 当前模式（只使用 rule_id + name + description）
                - "plan_a": 方案A - 精简版（提取【检查要点】）
                - "plan_b": 方案B - 完整版（使用完整 custom_prompt）
                - "plan_c": 方案C - 平衡版（提取【检查要点】+【判定逻辑】）

        Returns:
            完整的 Prompt 字符串

        Prompt 结构：
        1. 系统角色定义（资深病案质控专家）
        2. 文书类型和规则数量
        3. 规则清单（编号、名称、描述、检查要点）
        4. 病历内容（截取前 4000 字符）
        5. 输出要求

        优化说明：
        - 当前模式：只使用 rule_id + name + description
        - 方案 A（精简版）：为所有规则提取【检查要点】
        - 方案 B（完整版）：使用完整 custom_prompt
        - 方案 C（平衡版）：提取【检查要点】+【判定逻辑】
        - 增强策略：为复杂规则（如 LX-007、LX-009）额外提取【判定逻辑】
        """
        # 构建规则清单（根据 prompt_mode 决定提取内容）
        rules_text = ""
        rules_id_mapping_text = ""
        if rules:
            rules_text_lines = []
            rules_id_mapping_lines = []

            for i, rule in enumerate(rules):
                # GPT建议：使用 id 字段兜底，避免 None
                rule_id = rule.get('rule_id') or rule.get('id') or rule.get('rule_code') or f"RULE_{i+1}"
                rule_name = rule.get('name', '未命名规则')
                rule_desc = rule.get('description', '无描述')
                custom_prompt = rule.get('custom_prompt', '')

                # 根据 prompt_mode 提取不同的内容
                guidance = ""
                if prompt_mode == "current":
                    # 当前模式：不提取任何额外内容
                    guidance = ""
                elif prompt_mode == "plan_a":
                    # 方案 A：提取检查要点（+ 复杂规则增强）
                    guidance = self._extract_enhanced_guidance(custom_prompt, rule_id)
                elif prompt_mode == "plan_b":
                    # 方案 B：使用完整 custom_prompt
                    guidance = custom_prompt
                elif prompt_mode == "plan_c":
                    # 方案 C：提取检查要点 + 判定逻辑
                    guidance = self._extract_core_guidance(custom_prompt)
                else:
                    # 默认使用方案 A
                    guidance = self._extract_enhanced_guidance(custom_prompt, rule_id)

                # 规则清单：序号 + rule_id + 名称 + 描述 + 额外指导
                if guidance:
                    rules_text_lines.append(
                        f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}\n\n{guidance}"
                    )
                else:
                    # 如果没有额外指导，使用原有格式
                    rules_text_lines.append(
                        f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}"
                    )

                # 规则ID映射：明确的序号到 rule_id 的对应关系
                rules_id_mapping_lines.append(
                    f"  - 第{i+1}条 → rule_id: \"{rule_id}\""
                )

            rules_text = "\n\n".join(rules_text_lines)  # 使用双换行分隔规则，提高可读性
            rules_id_mapping_text = "\n".join(rules_id_mapping_lines)

            # 统计提取情况
            rules_with_guidance = sum(1 for rule in rules if self._extract_enhanced_guidance(rule.get('custom_prompt', ''), rule.get('rule_id', '')))
            logger.info(f"快速质控提示词构建: 共 {len(rules)} 条规则, {rules_with_guidance} 条包含检查要点")
        else:
            rules_text = "（未加载到具体规则，将进行通用质控分析）"
            rules_id_mapping_text = "（无规则映射）"

        # 优化后的 Prompt 模板 - 要求严格的 JSON 格式输出
        base_template = """你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 质控任务
文书类型: {document_type}
适用规则数: {rules_count}

## 质控规则清单
{rules_text}

## 规则ID映射
{rules_id_mapping}

## 病历内容
{content}

## 输出要求

**⚠️ 硬性约束（必须严格遵守）：**
1. **必须输出恰好 {rules_count} 个JSON对象**，不得多也不得少
2. **输出顺序必须与【质控规则清单】完全一致**，第1个对象对应第1条规则，第2个对象对应第2条规则，依此类推
3. **每条规则必须单独评估**，即使多条规则看起来相似，也不得合并输出
4. **每个JSON对象必须包含准确的rule_id**，对应关系见【规则ID映射】
5. **即使某条规则不适用当前文书，也必须输出对象**，is_compliant设为true，findings注明"不适用于当前文书类型"

**JSON对象格式：**
每条规则的评估结果必须包含以下字段：
- `rule_id`: 规则编号（字符串，**必填**，对应【规则ID映射】）
- `rule_name`: 规则名称（字符串）
- `is_compliant`: 是否符合规则（布尔值，true 或 false）
- `findings`: 评估发现（字符串，如果不符合，必须详细说明具体违反了哪个要求）
- `evidence`: 原文证据（字符串，**不符合时必须从病历中直接引用具体文本片段**）
- `location`: 问题定位（字符串，指出问题在病历的哪个部分）
- `suggestion`: 整改建议（字符串，不符合时给出具体的、可操作的改进建议）
- `confidence`: 评估置信度（浮点数，0.0-1.0之间）

**JSON 输出示例：**
```json
[
  {{
    "rule_id": "SC-001",
    "rule_name": "主诉应简明扼要",
    "is_compliant": false,
    "findings": "主诉过于冗长，包含了详细的病史描述，不符合'简明扼要'的要求",
    "evidence": "患者主诉：'反复胸痛、胸闷3年，加重伴气促1周。患者3年前无明显诱因出现胸痛...'（共120字）",
    "location": "主诉部分",
    "suggestion": "将主诉精简为：'反复胸痛、胸闷3年，加重伴气促1周'，详细病史移至现病史部分",
    "confidence": 0.95
  }},
  {{
    "rule_id": "SC-002",
    "rule_name": "现病史应包含起病时间",
    "is_compliant": true,
    "findings": "现病史明确记录了起病时间'3年前'和加重时间'1周前'",
    "evidence": "现病史：患者3年前无明显诱因出现胸痛...",
    "location": "现病史部分",
    "suggestion": "",
    "confidence": 0.98
  }}
]
```

**自检清单（输出前请确认）：**
- [ ] 输出了 {rules_count} 个对象？
- [ ] 顺序与规则清单一致？
- [ ] 每个对象都有rule_id？
- [ ] 不符合的规则都有evidence引用？

不要在 JSON 前后添加任何说明文字，直接输出 JSON 数组："""

        # 根据配置决定是否截断病历内容
        if self.enable_truncate:
            processed_content = self._smart_truncate(content, max_length=self.max_content_length)
            logger.info(f"智能截断已启用: 原始长度 {len(content)} → 处理后长度 {len(processed_content)}")
        else:
            processed_content = content
            logger.info(f"截断已禁用: 使用完整病历内容（长度 {len(content)} 字符）")

        prompt = base_template.format(
            document_type=document_type,
            rules_count=len(rules),
            rules_text=rules_text,
            rules_id_mapping=rules_id_mapping_text,
            content=processed_content
        )

        return prompt

    def _parse_llm_json_response(self, llm_output: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        解析 LLM 返回的 JSON 格式评估结果

        Args:
            llm_output: LLM 原始输出文本
            rules: 适用规则列表（用于降级处理）

        Returns:
            解析后的评估结果列表，每条包含：
            - rule_id, rule_name, is_compliant, findings, evidence, location, suggestion, confidence
        """
        import json
        import re

        try:
            # 尝试提取 JSON 数组部分
            # 查找第一个 [ 和最后一个 ]
            json_start = llm_output.find('[')
            json_end = llm_output.rfind(']')

            if json_start == -1 or json_end == -1 or json_start >= json_end:
                logger.warning(f"LLM 输出中未找到有效的 JSON 数组边界")
                logger.debug(f"LLM 原始输出: {llm_output[:500]}...")
                return self._create_fallback_results(llm_output, rules)

            json_str = llm_output[json_start:json_end + 1]

            # 尝试解析 JSON
            parsed_results = json.loads(json_str)

            if not isinstance(parsed_results, list):
                logger.warning(f"LLM 返回的 JSON 不是数组格式")
                return self._create_fallback_results(llm_output, rules)

            # 验证和规范化每条结果
            normalized_results = []
            for idx, item in enumerate(parsed_results):
                if not isinstance(item, dict):
                    logger.warning(f"跳过非字典格式的结果项 #{idx}")
                    continue

                # 提取并规范化字段
                normalized_item = {
                    'rule_id': str(item.get('rule_id', f'RULE_{idx+1}')),
                    'rule_name': str(item.get('rule_name', '未命名规则')),
                    'is_compliant': bool(item.get('is_compliant', True)),
                    'findings': str(item.get('findings', '')),
                    'evidence': str(item.get('evidence', '')),
                    'location': str(item.get('location', '')),
                    'suggestion': str(item.get('suggestion', '')),
                    'confidence': float(item.get('confidence', 0.75))
                }

                normalized_results.append(normalized_item)

            if len(normalized_results) == 0:
                logger.warning(f"解析后的结果为空，使用降级方案")
                return self._create_fallback_results(llm_output, rules)

            logger.info(f"✅ 成功解析 LLM JSON 响应，共 {len(normalized_results)} 条规则评估结果")
            return normalized_results

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.debug(f"尝试解析的 JSON 字符串: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
            return self._create_fallback_results(llm_output, rules)
        except Exception as e:
            logger.error(f"解析 LLM 响应时发生未知错误: {e}")
            return self._create_fallback_results(llm_output, rules)

    def _create_fallback_results(self, llm_output: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        当 JSON 解析失败时，创建降级结果

        Args:
            llm_output: LLM 原始输出
            rules: 适用规则列表

        Returns:
            降级的评估结果列表
        """
        logger.warning(f"使用降级方案生成评估结果")

        # 创建一条汇总结果
        fallback_results = [{
            'rule_id': 'SUMMARY',
            'rule_name': '质控分析汇总',
            'is_compliant': True,  # 默认符合，避免误报
            'findings': '模型返回了非结构化的分析结果，请查看原始输出',
            'evidence': llm_output[:200] if llm_output else '（无输出）',
            'location': '整体评估',
            'suggestion': '建议人工复核质控结果',
            'confidence': 0.5
        }]

        return fallback_results

    async def evaluate_document(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        对单个病历文档进行质控评估。

        Args:
            document_id: 文档 ID
            content: 病历内容
            document_type: 文书类型（默认为 "病程记录"）
            rule_ids: 可选的规则ID列表，用于过滤只评估指定的规则

        Returns:
            质控评估结果，包含：
            - document_id: 文档 ID
            - document_type: 文书类型
            - total_rules: 适用规则总数
            - applicable_rules: 适用规则代码列表
            - evaluation_summary: 评估摘要
            - llm_output: LLM 原始输出
            - token_usage: Token 使用量
            - api_time: API 调用时间
        """
        # P0 任务 1: 从数据库加载规则（按文书类型）
        rules = await self._load_rules_from_db(document_type)

        # 如果指定了 rule_ids，优先按 ID 精确取规则（支持 SC-/LX- 前缀跨来源）
        if rule_ids and len(rule_ids) > 0:
            selected_rules: List[Dict[str, Any]] = []
            for rid in rule_ids:
                try:
                    rule = self.get_rule_by_id(str(rid))
                    if rule:
                        selected_rules.append(rule)
                except Exception as e:
                    logger.warning(f"get_rule_by_id 失败: {rid} -> {e}")
            if selected_rules:
                rules = selected_rules
                logger.info(f"Selected {len(rules)} rules via get_rule_by_id from IDs: {rule_ids}")
            else:
                # 回退：在已加载的规则集中按 ID 过滤（保持与旧行为兼容）
                rules = [
                    r for r in rules
                    if r.get("rule_id") in rule_ids or r.get("rule_code") in rule_ids or r.get("id") in rule_ids
                ]
                logger.info(f"Filtered to {len(rules)} rules based on rule_ids within loaded set: {rule_ids}")

        # 使用统一规则引擎逐条执行
        rule_results, total_tokens, total_api_time = await self._evaluate_rules_with_engine(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=rules
        )

        total_rules = len(rules)
        compliant_rules = sum(
            1 for r in rule_results
            if r.get("status") in ("compliant", "not_applicable")
        )
        not_applicable_count = sum(1 for r in rule_results if r.get("status") == "not_applicable")
        issues_found = sum(1 for r in rule_results if r.get("status") == "non_compliant")
        compliance_rate = (compliant_rules / total_rules * 100.0) if total_rules else 100.0

        evaluation_results = []
        for item in rule_results:
            evaluation_results.append({
                "rule_id": item.get("rule_id"),
                "rule_name": item.get("rule_name"),
                "is_compliant": item.get("is_compliant"),
                "status": item.get("status"),
                "findings": item.get("findings"),
                "evidence": item.get("evidence"),
                "suggestion": item.get("suggestion"),
                "confidence": item.get("confidence"),
                "applicability": item.get("applicability"),
                "evidence_verified": item.get("evidence_verified"),
                "metadata": item.get("metadata"),
            })

        logger.info(
            f"质控评估完成: {compliant_rules}/{total_rules} 条规则符合（含不适用），合规率 {compliance_rate:.1f}%"
        )

        return {
            "document_id": document_id,
            "document_type": document_type,
            "total_rules": total_rules,
            "applicable_rules": [r.get("rule_code", r.get("id", "")) for r in rules],
            "evaluation_summary": {
                "compliance_rate": round(compliance_rate, 2),
                "issues_found": issues_found,
                "not_applicable": not_applicable_count,
                "total_rules": total_rules,
                "compliant_rules": compliant_rules,
                "model": self.client.model,
            },
            "parsed_evaluation_results": rule_results,
            "evaluation_results": evaluation_results,
            "llm_output": None,
            "token_usage": {"total_tokens": total_tokens},
            "api_time": total_api_time,
        }

    async def evaluate_batch(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for doc in documents:
            out.append(
                await self.evaluate_document(
                    document_id=doc.get("document_id", "unknown"),
                    content=doc.get("content", ""),
                    document_type=doc.get("document_type", "病程记录"),
                )
            )
        return out

    async def evaluate_document_fast(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None,
        prompt_mode: str = "plan_a"
    ) -> Dict[str, Any]:
        """
        快速质控模式：一次性调用 LLM 评估所有规则（批量模式）

        与 evaluate_document 的区别：
        - evaluate_document: 逐条规则调用 LLM（串行模式）
        - evaluate_document_fast: 一次调用评估所有规则（快速模式）

        Args:
            document_id: 文档 ID
            content: 病历内容
            document_type: 文书类型（默认为 "病程记录"）
            rule_ids: 可选的规则ID列表，用于过滤只评估指定的规则
            prompt_mode: 提示词优化方案（current/plan_a/plan_b/plan_c）

        Returns:
            质控评估结果
        """
        # 1. 加载规则
        if rule_ids and len(rule_ids) > 0:
            # 与串行模式保持一致：优先通过 get_rule_by_id 精确加载规则
            selected_rules: List[Dict[str, Any]] = []
            for rid in rule_ids:
                try:
                    rule = self.get_rule_by_id(str(rid))
                    if rule:
                        selected_rules.append(rule)
                except Exception as e:
                    logger.warning(f"get_rule_by_id 失败: {rid} -> {e}")

            if selected_rules:
                rules = selected_rules
                logger.info(f"Selected {len(rules)} rules via get_rule_by_id from IDs: {rule_ids}")
            else:
                # 回退：从数据库按文书类型加载，再按 rule_ids 过滤
                rules = await self._load_rules_from_db(document_type)
                rules = [
                    r for r in rules
                    if r.get("rule_id") in rule_ids or r.get("rule_code") in rule_ids or r.get("id") in rule_ids
                ]
                logger.info(f"Filtered to {len(rules)} rules based on rule_ids within loaded set: {rule_ids}")
        else:
            rules = await self._load_rules_from_db(document_type)

        if not rules:
            logger.warning(f"未找到适用的规则: document_type={document_type}, rule_ids={rule_ids}")
            return {
                "document_id": document_id,
                "evaluation_summary": {
                    "compliance_rate": 100.0,
                    "issues_found": 0,
                    "model": self.client.model
                },
                "evaluation_results": [],
                "performance_metrics": {
                    "token_usage": 0,
                    "estimated_cost": 0.0
                },
                "total_rules": 0,
                "llm_output": "未找到适用的规则"
            }

        # 3. 构建批量提示词（传递 prompt_mode）
        prompt = await self._build_prompt(rules, content, document_type, prompt_mode)

        # 4. 调用 LLM（一次性评估所有规则）
        api_start = time.time()
        llm_response = await self.client.generate(prompt)
        api_time = time.time() - api_start

        # 5. 解析响应
        llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        token_usage = llm_response.get("usage", {}).get("total_tokens", 0)

        # 6. 解析 JSON 结果
        try:
            evaluation_results = self._parse_llm_json_response(llm_output, rules)
        except Exception as e:
            logger.error(f"解析 LLM 响应失败: {e}")
            evaluation_results = []

        # 7. 计算统计信息
        total_rules = len(rules)
        compliant_rules = sum(
            1 for r in evaluation_results
            if r.get("is_compliant") is True or r.get("status") in ("compliant", "not_applicable")
        )
        issues_found = total_rules - compliant_rules
        compliance_rate = (compliant_rules / total_rules * 100) if total_rules > 0 else 100.0

        # 8. 计算成本（假设 ¥0.002/1000 tokens）
        estimated_cost = (token_usage / 1000) * 0.002

        return {
            "document_id": document_id,
            "document_type": document_type,
            "total_rules": total_rules,
            "prompt_mode": prompt_mode,  # 添加 prompt_mode 到返回结果
            "evaluation_summary": {
                "total_rules": total_rules,
                "compliant_rules": compliant_rules,
                "issues_found": issues_found,
                "compliance_rate": compliance_rate,
                "model": self.client.model
            },
            "evaluation_results": evaluation_results,
            "performance_metrics": {
                "token_usage": token_usage,
                "api_time": api_time,
                "estimated_cost": estimated_cost
            },
            "llm_output": llm_output
        }

    def stats(self) -> Dict[str, Any]:
        return self.client.stats()

    async def evaluate_multi_document(
        self,
        document_id: str,
        document_content: str,
        document_types: Optional[List[str]] = None,
        preclassified_documents: Optional[Dict[str, Any]] = None,
        rules_by_document_type: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        # Build document map: {doc_type: content}
        def extract_text(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, list):
                return "\n\n".join(extract_text(v) for v in val)
            if isinstance(val, dict):
                # Common shapes: {content: text} or {sections: [...]}
                if "content" in val:
                    return extract_text(val["content"])
                if "sections" in val and isinstance(val["sections"], list):
                    return "\n\n".join(extract_text(s) for s in val["sections"])
                return "\n".join(f"{k}: {extract_text(v)}" for k, v in val.items())
            return str(val)

        doc_map: Dict[str, str] = {}
        if preclassified_documents:
            for k, v in preclassified_documents.items():
                doc_map[k] = extract_text(v)
        elif document_types:
            for t in document_types:
                doc_map[t] = document_content
        else:
            doc_map["病程记录"] = document_content

        n_docs = max(1, len(doc_map))

        # P0 任务 1: 从数据库加载规则（如果未提供预加载的规则）
        # 如果前端提供了 rules_by_document_type，优先使用
        # 否则，从数据库动态加载每种文书类型的规则
        if not rules_by_document_type:
            rules_by_document_type = {}
            for doc_type in doc_map.keys():
                rules_by_document_type[doc_type] = await self._load_rules_from_db(doc_type)
            logger.info(f"Loaded rules from database for {len(rules_by_document_type)} document types")

        document_results: Dict[str, Any] = {}
        total_tokens = 0
        total_time = 0.0
        sum_total_rules = 0
        sum_compliant = 0
        sum_not_applicable = 0
        sum_critical = 0

        for doc_type, text in doc_map.items():
            doc_rules = rules_by_document_type.get(doc_type, [])
            rule_results, tokens, api_time = await self._evaluate_rules_with_engine(
                document_id=document_id,
                content=text,
                document_type=doc_type,
                rules=doc_rules
            )

            total_rules = len(doc_rules)
            compliant = sum(
                1 for r in rule_results
                if r.get("status") in ("compliant", "not_applicable")
            )
            not_applicable = sum(1 for r in rule_results if r.get("status") == "not_applicable")
            critical_violations = sum(1 for r in rule_results if r.get("status") == "non_compliant")

            sum_total_rules += total_rules
            sum_compliant += compliant
            sum_not_applicable += not_applicable
            sum_critical += critical_violations
            total_tokens += tokens
            total_time += api_time

            document_results[doc_type] = {
                "total_rules": total_rules,
                "compliant_rules": compliant,
                "not_applicable": not_applicable,
                "processing_time": api_time,
                "token_usage": tokens,
                "critical_violations": critical_violations,
                "evaluation_results": rule_results,
            }

        overall_rate = (sum_compliant / max(sum_total_rules, 1)) * 100
        overall_grade = "A" if overall_rate >= 90 else "B" if overall_rate >= 75 else "C"
        document_breakdown = {}
        for dt, dr in document_results.items():
            total = dr.get("total_rules", 0)
            compliant = dr.get("compliant_rules", 0)
            document_breakdown[dt] = {
                "total_rules": total,
                "compliant_rules": compliant,
                "compliance_rate": round((compliant / total * 100) if total else 100.0, 2),
                "critical_violations": dr.get("critical_violations", 0),
                "not_applicable": dr.get("not_applicable", 0),
            }

        optimization_metrics = {
            "token_savings_rate": 0.0,
            "estimated_original_tokens": total_tokens,
            "actual_tokens_saved": 0,
            "cost_savings": 0.0,
        }

        return {
            "document_id": document_id,
            "overall_summary": {
                "total_rules": sum_total_rules,
                "compliant_rules": sum_compliant,
                "not_applicable": sum_not_applicable,
                "issues_found": sum_critical,
                "compliance_rate": round(overall_rate, 2),
                "overall_grade": overall_grade,
                "critical_violations": sum_critical,
                "document_breakdown": document_breakdown,
            },
            "total_processing_time": total_time,
            "total_token_usage": total_tokens,
            "optimization_metrics": optimization_metrics,
            "document_results": document_results,
        }

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """
        根据规则ID获取单个规则（支持四川省规则和自定义规则）

        Args:
            rule_id: 规则ID（如 "SC-010" 或 "LX-011"）

        Returns:
            规则对象，如果未找到则返回 None
        """
        # 根据规则ID前缀明确区分规则来源
        # SC- 开头：四川省规则（sichuan_rules_146.json）
        # LX- / LXE- 开头：泸县自定义规则（custom_rules_33.json）
        if rule_id.startswith("SC-"):
            all_rules = self._load_rules_from_json()
        elif rule_id.startswith("LX-") or rule_id.startswith("LXE-"):
            all_rules = self._load_custom_rules_from_json()
        else:
            logger.warning(f"未知的规则ID前缀: {rule_id}")
            return None

        for rule in all_rules:
            if rule.get("rule_id") == rule_id:
                return rule
        return None

    def update_rule_prompt(self, rule_id: str, custom_prompt: Optional[str]) -> bool:
        """
        更新规则的自定义提示词（支持四川省规则和自定义规则）

        Args:
            rule_id: 规则ID（如 "SC-010" 或 "LX-011"）
            custom_prompt: 自定义提示词，如果为 None 则删除自定义提示词

        Returns:
            是否更新成功
        """
        import json
        import os

        # 根据规则ID前缀明确确定要更新的文件
        # SC- 开头：四川省规则（sichuan_rules_146.json）
        # LX- 开头：自定义规则（custom_rules_33.json）
        if rule_id.startswith("SC-"):
            json_filename = "sichuan_rules_146.json"
        elif rule_id.startswith("LX-"):
            json_filename = "custom_rules_33.json"
        else:
            logger.warning(f"未知的规则ID前缀: {rule_id}")
            return False

        json_path = os.path.join(
            os.path.dirname(__file__),
            "..", "data", json_filename
        )

        try:
            # 读取所有规则
            with open(json_path, "r", encoding="utf-8") as f:
                rules = json.load(f)

            # 查找并更新指定规则
            rule_found = False
            for rule in rules:
                if rule.get("rule_id") == rule_id:
                    if custom_prompt is None:
                        # 删除自定义提示词
                        rule.pop("custom_prompt", None)
                    else:
                        # 设置自定义提示词
                        rule["custom_prompt"] = custom_prompt
                    rule_found = True
                    break

            if not rule_found:
                return False

            # 保存回文件
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)

            # 清除缓存，强制下次重新加载
            if rule_id.startswith("SC-"):
                self._rules_cache = None

            logger.info(f"成功更新规则 {rule_id} 的提示词（文件：{json_filename}）")
            return True

        except Exception as e:
            logger.error(f"更新规则提示词失败: {e}", exc_info=True)
            return False
