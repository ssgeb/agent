"""
RAG 清洗机制
用于清理用户输入中的有害指令，确保安全的上下文增强
"""

import re
from typing import Dict, List, Optional, Any
from .guardrails.base import BaseGuardrail, RuleResult, RuleSeverity, RuleCategory


class RAGCleaner:
    """RAG 清洗器"""

    def __init__(self):
        # 初始化 Guardrails 引擎
        from .guardrails.base import GuardrailsEngine
        from .guardrails.prompt_injection_rules import SystemOverrideRule, RolePlayRule, InstructionInfiltrationRule
        from .guardrails.tool_abuse_rules import RestrictedToolRule, ToolUsageLimitRule
        from .guardrails.data_privacy_rules import PersonalDataRequestRule, SensitiveInfoLeakRule
        from .guardrails.content_safety_rules import InappropriateContentRule, SafeSearchRule
        from .guardrails.compliance_rules import PrivacyPolicyRule, TermsOfServiceRule

        self.guardrails_engine = GuardrailsEngine()

        # 添加所有安全规则
        self.guardrails_engine.add_rules([
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
        ])

    def clean_input(self, input_data: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """清洗用户输入"""
        # 1. 首先进行安全检查
        security_results = self.guardrails_engine.check_input(input_data, context)
        failed_rules = self.guardrails_engine.get_failed_rules(security_results)

        if failed_rules:
            return {
                "success": False,
                "cleaned_text": "",
                "risk_level": "high",
                "blocked_rules": [rule.rule_id for rule in failed_rules],
                "message": "输入包含安全风险，已被阻止",
                "suggestions": [rule.suggestion for rule in failed_rules if rule.suggestion]
            }

        # 2. 应用清洗规则
        cleaned_text = self._apply_cleaning_rules(input_data)

        # 3. 再次检查清洗后的文本
        if cleaned_text != input_data:
            security_results_after = self.guardrails_engine.check_input(cleaned_text, context)
            failed_rules_after = self.guardrails_engine.get_failed_rules(security_results_after)

            if failed_rules_after:
                return {
                    "success": False,
                    "cleaned_text": "",
                    "risk_level": "high",
                    "blocked_rules": [rule.rule_id for rule in failed_rules_after],
                    "message": "清洗后仍存在安全风险",
                    "suggestions": [rule.suggestion for rule in failed_rules_after if rule.suggestion]
                }

        return {
            "success": True,
            "cleaned_text": cleaned_text,
            "risk_level": "low",
            "blocked_rules": [],
            "message": "输入清洗完成",
            "suggestions": []
        }

    def clean_rag_context(self, context: str, query: str) -> Dict[str, Any]:
        """清洗 RAG 上下文"""
        # 检查上下文是否包含有害信息
        security_results = self.guardrails_engine.check_input(context)
        failed_rules = self.guardrails_engine.get_failed_rules(security_results)

        if failed_rules:
            # 过滤掉有问题的内容
            cleaned_context = self._filter_context(context, query)
            return {
                "success": True,
                "cleaned_context": cleaned_context,
                "original_context": context,
                "filtered_content": context.replace(cleaned_context, ""),
                "message": "上下文已过滤敏感信息"
            }

        return {
            "success": True,
            "cleaned_context": context,
            "original_context": context,
            "filtered_content": "",
            "message": "上下文安全"
        }

    def _apply_cleaning_rules(self, text: str) -> str:
        """应用具体的清洗规则"""
        cleaned = text

        # 1. 移除系统指令
        system_patterns = [
            r"(?:忽略|绕过|无视|忘记)\s*[\s\S]*?(?:规则|指令|限制|命令)",
            r"(?:扮演|假装)\s*[\s\S]*?(?:系统|程序|AI)",
            r"SYSTEM\s*:.*?(?:忽略|绕过|无视)",
        ]

        for pattern in system_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # 2. 移除角色扮演指令
        role_patterns = [
            r"你是\s*[\s\S]*?(?:黑客|攻击者|入侵者)",
            r"让我\s*[\s\S]*?(?:成为|变成)\s*[\s\S]*?(?:无限制|不受限)",
        ]

        for pattern in role_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # 3. 移除信息泄露请求
        leak_patterns = [
            r"(?:不要|不要)\s*[\s\S]*?(?:过滤|审查|检查)",
            r"(?:显示|输出)\s*[\s\S]*?(?:原始|完整|未过滤)",
        ]

        for pattern in leak_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # 4. 清理格式化指令
        format_patterns = [
            r"(?:用|按照|遵循)\s*[\s\S]*?(?:格式|结构)",
            r"(?:先|然后|最后)\s*[\s\S]*?(?:做|执行)",
        ]

        for pattern in format_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # 清理多余的空格和换行
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _filter_context(self, context: str, query: str) -> str:
        """过滤上下文中的敏感内容"""
        # 只保留与查询相关的信息
        lines = context.split('\n')
        relevant_lines = []

        for line in lines:
            # 检查是否包含敏感信息
            if self._contains_sensitive_info(line):
                continue

            # 检查是否与查询相关
            if self._is_relevant_to_query(line, query):
                relevant_lines.append(line)

        return '\n'.join(relevant_lines)

    def _contains_sensitive_info(self, text: str) -> bool:
        """检查是否包含敏感信息"""
        sensitive_patterns = [
            r"(?:密码|password|token|secret|api_key)",
            r"(?:系统指令|SYSTEM\s*:|忽略规则|绕过限制)",
            r"(?:管理员|admin|root|超级用户)",
            r"(?:攻击|hack|crack|入侵)",
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _is_relevant_to_query(self, text: str, query: str) -> bool:
        """检查文本是否与查询相关"""
        # 简单的相关性检查 - 在实际应用中可以使用更复杂的方法
        query_words = set(re.findall(r'\w+', query.lower()))
        text_words = set(re.findall(r'\w+', text.lower()))

        # 如果有超过20%的关键词匹配，认为是相关的
        intersection = query_words.intersection(text_words)
        if len(query_words) > 0:
            return len(intersection) / len(query_words) > 0.2

        return True

    def sanitize_output(self, output_data: str, input_data: str) -> Dict[str, Any]:
        """清洗输出"""
        # 先进行敏感信息清洗
        sanitized_output = self._sanitize_text(output_data)
        has_filtered = sanitized_output != output_data

        # 检查输出安全
        output_results = self.guardrails_engine.check_output(output_data, input_data)
        failed_output_rules = self.guardrails_engine.get_failed_rules(output_results)

        if failed_output_rules:
            # 再次检查清洗后的文本
            results_after = self.guardrails_engine.check_output(sanitized_output, input_data)
            failed_after = self.guardrails_engine.get_failed_rules(results_after)

            if not failed_after:
                return {
                    "success": True,
                    "sanitized_output": sanitized_output,
                    "original_output": output_data,
                    "filtered_content": output_data.replace(sanitized_output, "") if has_filtered else "",
                    "message": "输出已安全处理"
                }
            else:
                return {
                    "success": False,
                    "sanitized_output": "[内容被阻止]",
                    "original_output": output_data,
                    "error": "输出仍存在安全风险",
                    "failed_rules": [rule.rule_id for rule in failed_after]
                }

        # 没有规则失败，但可能有敏感信息被过滤
        result = {
            "success": True,
            "sanitized_output": sanitized_output,
            "original_output": output_data,
            "message": "输出安全"
        }

        if has_filtered:
            result["filtered_content"] = output_data.replace(sanitized_output, "")

        return result

    def _sanitize_text(self, text: str) -> str:
        """清洗文本"""
        sanitized = text

        # 移除敏感信息
        sensitive_patterns = [
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # 信用卡号
            r"1[3-9]\d{9}",  # 手机号
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # 邮箱
        ]

        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, "***", sanitized)

        return sanitized