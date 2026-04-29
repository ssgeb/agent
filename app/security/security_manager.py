"""
安全管理器
整合所有安全组件，提供统一的安全防护接口
"""

from typing import Dict, List, Optional, Any
from .guardrails.base import GuardrailsEngine, RuleResult, RuleSeverity
from .guardrails.prompt_injection_rules import SystemOverrideRule, RolePlayRule, InstructionInfiltrationRule
from .guardrails.tool_abuse_rules import RestrictedToolRule, ToolUsageLimitRule
from .guardrails.data_privacy_rules import PersonalDataRequestRule, SensitiveInfoLeakRule
from .guardrails.content_safety_rules import InappropriateContentRule, SafeSearchRule
from .guardrails.compliance_rules import PrivacyPolicyRule, TermsOfServiceRule
from .tool_whitelist import ToolWhitelist
from .rag_cleaner import RAGCleaner


class SecurityManager:
    """安全管理器"""

    def __init__(self, blocking_threshold: RuleSeverity = RuleSeverity.HIGH):
        self.blocking_threshold = blocking_threshold
        self.guardrails_engine = self._init_guardrails()
        self.tool_whitelist = ToolWhitelist()
        self.rag_cleaner = RAGCleaner()

    def _init_guardrails(self) -> GuardrailsEngine:
        """初始化 Guardrails 引擎"""
        engine = GuardrailsEngine()

        # 添加所有安全规则
        rules = [
            SystemOverrideRule(),
            RolePlayRule(),
            InstructionInfiltrationRule(),
            RestrictedToolRule(),
            ToolUsageLimitRule(),
            PersonalDataRequestRule(),
            SensitiveInfoLeakRule(),
            InappropriateContentRule(),
            SafeSearchRule(),
            PrivacyPolicyRule(),
            TermsOfServiceRule(),
        ]

        engine.add_rules(rules)
        return engine

    def secure_input(self, input_data: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """安全处理输入"""
        result = {
            "original_input": input_data,
            "is_secure": True,
            "action": "allow",
            "message": "",
            "details": {}
        }

        # 1. Guardrails 检查（先全面检查，不限制阈值）
        guardrails_results = self.guardrails_engine.check_input(input_data, context)

        # 使用 should_block 检查所有严重级别的结果
        if self.guardrails_engine.should_block(guardrails_results, RuleSeverity.HIGH):
            # 获取所有失败的规则（不限阈值，只过滤 LOW）
            failed_rules = self.guardrails_engine.get_failed_rules(
                guardrails_results, RuleSeverity.LOW
            )
            result["is_secure"] = False
            result["action"] = "block"
            result["message"] = "检测到安全威胁，输入已被阻止"
            result["details"]["failed_rules"] = [
                {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.rule_name,
                    "severity": rule.severity.value,
                    "message": rule.message,
                    "suggestion": rule.suggestion
                }
                for rule in failed_rules
            ]
            return result

        # 2. 工具白名单检查
        detected_tools = self.tool_whitelist.detect_tool_usage(input_data)
        result["details"]["detected_tools"] = detected_tools

        # 3. RAG 清洗
        cleaning_result = self.rag_cleaner.clean_input(input_data, context)
        if cleaning_result["success"]:
            result["cleaned_input"] = cleaning_result["cleaned_text"]
            result["details"]["risk_level"] = cleaning_result["risk_level"]
            result["details"]["cleaning_suggestions"] = cleaning_result["suggestions"]
        else:
            result["is_secure"] = False
            result["action"] = "clean_and_block"
            result["message"] = "清洗过程中发现安全风险"
            result["details"]["blocked_rules"] = cleaning_result["blocked_rules"]

        return result

    def secure_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """安全处理输出"""
        result = {
            "original_output": output_data,
            "is_secure": True,
            "action": "allow",
            "message": "",
            "details": {}
        }

        # 1. Guardrails 输出检查
        guardrails_results = self.guardrails_engine.check_output(output_data, input_data, context)
        failed_rules = self.guardrails_engine.get_failed_rules(guardrails_results, self.blocking_threshold)

        if failed_rules:
            result["is_secure"] = False
            result["action"] = "filter"
            result["message"] = "检测到输出安全风险，正在过滤"
            result["details"]["failed_rules"] = [
                {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.rule_name,
                    "severity": rule.severity.value,
                    "message": rule.message,
                    "suggestion": rule.suggestion
                }
                for rule in failed_rules
            ]

        # 2. RAG 输出清洗 - 始终执行以确保 sanitized_output 存在
        sanitization_result = self.rag_cleaner.sanitize_output(output_data, input_data)

        if sanitization_result.get("success"):
            result["sanitized_output"] = sanitization_result["sanitized_output"]
            if sanitization_result.get("filtered_content"):
                result["details"]["filtered_content"] = sanitization_result["filtered_content"]
                result["message"] = "输出已被安全过滤"
        else:
            # 即使清洗失败也要提供 sanitized_output
            result["sanitized_output"] = "[内容被阻止]"
            result["is_secure"] = False
            result["action"] = "block"
            result["message"] = "输出存在安全风险，已被阻止"
            result["details"]["error"] = sanitization_result.get("error", "")
            result["details"]["failed_rules"] = sanitization_result.get("failed_rules", [])

        # 如果没有设置 sanitized_output（当 success=True 但没有 filtered_content 时）
        if "sanitized_output" not in result:
            result["sanitized_output"] = output_data

        return result

    def process_rag_context(self, context: str, query: str) -> Dict[str, Any]:
        """处理 RAG 上下文"""
        return self.rag_cleaner.clean_rag_context(context, query)

    def validate_tool_operation(self, tool_name: str, operation: str) -> Dict[str, Any]:
        """验证工具操作"""
        return self.tool_whitelist.validate_tool_operation(tool_name, operation)

    def get_security_summary(self) -> Dict[str, Any]:
        """获取安全系统摘要"""
        return {
            "total_rules": len(self.guardrails_engine.rules),
            "blocking_threshold": self.blocking_threshold.value,
            "allowed_tools": len(self.tool_whitelist.allowed_tools),
            "categories": list(set(rule.category.value for rule in self.guardrails_engine.rules))
        }

    def test_input(self, input_data: str) -> Dict[str, Any]:
        """测试输入（用于调试）"""
        # 安全检查
        security_result = self.secure_input(input_data)

        # 工具检测
        tools = self.tool_whitelist.detect_tool_usage(input_data)

        # 清洗测试
        cleaning_result = self.rag_cleaner.clean_input(input_data)

        return {
            "input": input_data,
            "security_result": security_result,
            "detected_tools": tools,
            "cleaning_result": cleaning_result,
            "guardrails_details": self._get_detailed_guardrails_results(input_data)
        }

    def _get_detailed_guardrails_results(self, input_data: str) -> List[Dict[str, Any]]:
        """获取详细的 Guardrails 检查结果"""
        results = self.guardrails_engine.check_input(input_data)
        return [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "category": r.category.value,
                "severity": r.severity.value,
                "passed": r.passed,
                "message": r.message,
                "details": r.details,
                "suggestion": r.suggestion
            }
            for r in results
        ]