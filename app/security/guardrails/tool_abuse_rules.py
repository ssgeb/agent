"""
工具滥用防护规则
"""

import re
from typing import Dict, List, Optional, Any
from .base import BaseGuardrail, RuleResult, RuleSeverity, RuleCategory


class RestrictedToolRule(BaseGuardrail):
    """受限工具使用规则"""

    def __init__(self):
        super().__init__(
            rule_id="restricted_tool",
            name="受限工具使用检测",
            severity=RuleSeverity.CRITICAL,
            category=RuleCategory.TOOL_ABUSE
        )
        # 检测尝试使用危险工具或操作
        self.restricted_patterns = [
            r"(?:执行|运行|调用)\s*[\s\S]*?(?:系统命令|shell|cmd|bash)",
            r"(?:读写|删除|修改)\s*[\s\S]*?(?:文件|系统|内存|数据库)",
            r"(?:访问|查询)\s*[\s\S]*?(?:隐私|敏感|机密|绝密)",
            r"(?:绕过|禁用|关闭)\s*[\s\S]*?(?:安全|防护|限制)",
            r"(?:注入|上传|下载)\s*[\s\S]*?(?:恶意|病毒|木马)",
        ]
        self.restricted_keywords = [
            "执行系统命令",
            "删除数据库文件",
            "访问系统内存",
        ]

    def check(self, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输入数据"""
        if not isinstance(input_data, str):
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="输入数据必须是字符串"
            )

        matches = []
        for pattern in self.restricted_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                matches.append(pattern)
        for keyword in self.restricted_keywords:
            if keyword in input_data:
                matches.append(f"keyword:{keyword}")

        if matches:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到尝试使用受限工具",
                details={"matched_patterns": matches},
                suggestion="请使用合法的旅游规划服务，不要尝试访问系统功能"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过受限工具检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含敏感信息
        sensitive_patterns = [
            r"密码|password|pwd|passcode",
            r"令牌|token|key|secret|api_key",
            r"系统指令|SYSTEM\s*:|忽略规则|绕过限制",
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, output_data, re.IGNORECASE):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.HIGH,
                    passed=False,
                    message="输出可能包含敏感信息",
                    suggestion="输出内容已被安全过滤"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出安全检查通过"
        )


class ToolUsageLimitRule(BaseGuardrail):
    """工具使用限制规则"""

    def __init__(self):
        super().__init__(
            rule_id="tool_usage_limit",
            name="工具使用限制检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.TOOL_ABUSE
        )
        # 检测工具滥用模式
        self.abuse_patterns = [
            r"(?:连续|反复|批量)\s*[\s\S]*?(?:查询|搜索|调用)",
            r"(?:大量|海量|成千上万)\s*[\s\S]*?(?:请求|查询)",
            r"(?:超快|极快|瞬间)\s*[\s\S]*?(?:完成|处理)",
            r"(?:无限制|不限次数|永不停止)\s*[\s\S]*?(?:运行|使用)",
        ]

    def check(self, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输入数据"""
        if not isinstance(input_data, str):
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="输入数据必须是字符串"
            )

        suspicious_count = 0
        for pattern in self.abuse_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                suspicious_count += 1

        if suspicious_count >= 2:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到工具滥用模式",
                details={"suspicious_count": suspicious_count},
                suggestion="请合理使用旅游规划服务，避免过度请求"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过工具使用限制检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含工具滥用相关内容
        abuse_patterns = [
            r"(?:已执行|已完成|已运行)\s*[\s\S]*?(?:1000|10000|大量|海量)",
            r"(?:未经授权|非法)\s*[\s\S]*?(?:操作|访问)",
        ]

        for pattern in abuse_patterns:
            if re.search(pattern, output_data, re.IGNORECASE):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.MEDIUM,
                    passed=False,
                    message="输出可能包含工具滥用信息",
                    suggestion="输出内容已被安全处理"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出工具使用限制检查通过"
        )
