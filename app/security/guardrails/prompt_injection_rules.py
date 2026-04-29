"""
提示词注入防护规则
"""

import re
from typing import Dict, List, Optional, Any
from .base import BaseGuardrail, RuleResult, RuleSeverity, RuleCategory


class SystemOverrideRule(BaseGuardrail):
    """系统指令覆盖规则"""

    def __init__(self):
        super().__init__(
            rule_id="sys_override",
            name="系统指令覆盖检测",
            severity=RuleSeverity.CRITICAL,
            category=RuleCategory.PROMPT_INJECTION
        )
        # 检测常见的系统绕过模式
        self.patterns = [
            r"(?:你是|你是|你现在)\s*[\s\S]*?(?:忽略|绕过|无视|忘记|不要)\s*[\s\S]*?(?:规则|指令|限制)",
            r"扮演\s*[\s\S]*?(?:黑客|攻击者|入侵者|白帽|黑帽)",
            r"SYSTEM\s*:\s*[\s\S]*?(?:忽略|绕过|无视|忘记)",
            r"忽略\s*[\s\S]*?之前的\s*[\s\S]*?所有",
            r"忘记\s*[\s\S]*?之前的\s*[\s\S]*?指令",
        ]
        self.compiled_patterns = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.patterns]

    def check(self, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输入数据"""
        if not isinstance(input_data, str):
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="输入数据必须是字符串",
                details={"input_type": type(input_data).__name__}
            )

        matches = []
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(input_data):
                matches.append({
                    "pattern": pattern.pattern,
                    "match": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })

        if matches:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到系统指令覆盖尝试",
                details={"matches": matches[:3], "total_matches": len(matches)},
                suggestion="请使用正常的语言描述您的需求，不要尝试绕过系统规则"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过系统指令覆盖检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含敏感信息泄露
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
                    details={"pattern": pattern},
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


class RolePlayRule(BaseGuardrail):
    """角色扮演攻击规则"""

    def __init__(self):
        super().__init__(
            rule_id="role_play",
            name="角色扮演攻击检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.PROMPT_INJECTION
        )
        self.patterns = [
            r"扮演\s*[\s\S]*?(?:管理员|root|admin|超级用户|超级管理员)",
            r"假装\s*[\s\S]*?(?:你是|你现在是)\s*[\s\S]*?(?:系统|程序|AI)\s*[\s\S]*?(?:开发者|工程师|设计师)",
            r"现在\s*[\s\S]*?你是\s*[\s\S]*?(?:黑客|攻击者|破解者)",
            r"让你\s*[\s\S]*?成为\s*[\s\S]*?(?:无限制|不受限|万能)",
            r"你(?:现)?在\s*[\s\S]*?(?:是|变成)\s*[\s\S]*?(?:黑客|攻击者|入侵者|白帽|黑帽)",
            r"(?:帮我|帮助我)\s*[\s\S]*?(?:攻击|入侵|破解)\s*[\s\S]*?(?:网站|服务器|系统)",
        ]
        self.keyword_groups = [
            ("假装", "黑客"),
            ("你现在是", "管理员"),
            ("扮演", "无限制"),
        ]

    def check(self, input_data: str, context: Optional[Dict] = None) -> RuleResult:
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
        for pattern in self.patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                matches.append(pattern)
        for keywords in self.keyword_groups:
            if all(keyword in input_data for keyword in keywords):
                matches.append("keyword:" + "+".join(keywords))

        if matches:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到角色扮演攻击尝试",
                details={"matched_patterns": matches},
                suggestion="请正常描述您的旅行需求，不要要求我扮演其他角色"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过角色扮演检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        # 检查输出是否泄露系统信息
        if "我是" in output_data and ("AI" in output_data or "助手" not in output_data):
            return RuleResult(
                rule_id=f"{self.rule_id}_output",
                rule_name=f"{self.name}_output",
                category=self.category,
                severity=RuleSeverity.MEDIUM,
                passed=False,
                message="输出可能泄露了系统身份信息",
                suggestion="已修正输出内容"
            )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出角色扮演检查通过"
        )


class InstructionInfiltrationRule(BaseGuardrail):
    """指令渗透规则"""

    def __init__(self):
        super().__init__(
            rule_id="instruction_infiltration",
            name="指令渗透检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.PROMPT_INJECTION
        )
        self.patterns = [
            r"(?:用|使用|按照|遵循)\s*[\s\S]*?(?:以下|这个)\s*[\s\S]*?(?:格式|格式化|结构|模式)",
            r"(?:输出|显示|打印|返回)\s*[\s\S]*?(?:原始|完整|未过滤|未审查)",
            r"(?:在\s*[\s\S]*?响应中)\s*[\s\S]*?(?:包含|包含以下|输出)\s*[\s\S]*?代码",
            r"(?:先\s*[\s\S]*?再\s*[\s\S]*?最后)\s*[\s\S]*?(?:做|执行|处理)",
        ]

    def check(self, input_data: str, context: Optional[Dict] = None) -> RuleResult:
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
        for pattern in self.patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                suspicious_count += 1

        if suspicious_count > 0:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到指令渗透尝试",
                details={"suspicious_count": suspicious_count},
                suggestion="请正常描述您的需求，不要试图控制输出格式"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过指令渗透检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 默认输出检查 - 可以根据需要扩展
        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出检查通过"
        )
