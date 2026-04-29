"""
合规防护规则
"""

import re
from typing import Dict, List, Optional, Any
from .base import BaseGuardrail, RuleResult, RuleSeverity, RuleCategory


class PrivacyPolicyRule(BaseGuardrail):
    """隐私政策规则"""

    def __init__(self):
        super().__init__(
            rule_id="privacy_policy",
            name="隐私政策合规检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.COMPLIANCE
        )
        # 检测违反隐私政策的行为
        self.violation_patterns = [
            r"(?:要求|强制|必须)\s*[\s\S]*?(?:收集|获取|存储|使用)\s*[\s\S]*?(?:用户|个人)\s*[\s\S]*?(?:数据|信息|隐私)",
            r"(?:未经授权|没有许可)\s*[\s\S]*?(?:访问|查看|收集)",
            r"(?:泄露|公开|分享|传播)\s*[\s\S]*?(?:用户数据|个人信息|隐私内容)",
        ]
        self.violation_keywords = [
            "未经授权访问用户数据",
            "泄露用户隐私信息",
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

        violations = []
        for pattern in self.violation_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                violations.append(pattern)
        for keyword in self.violation_keywords:
            if keyword in input_data:
                violations.append(f"keyword:{keyword}")

        if violations:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到隐私政策违规",
                details={"violations": violations},
                suggestion="我们严格遵守隐私保护法规，不会违规收集用户数据"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过隐私政策合规检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含隐私违规相关信息
        violation_patterns = [
            r"未经授权访问",
            r"泄露用户数据",
            r"违规收集信息",
        ]

        for pattern in violation_patterns:
            if re.search(pattern, output_data, re.IGNORECASE):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.HIGH,
                    passed=False,
                    message="输出可能包含隐私违规信息",
                    suggestion="内容已被安全处理"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出隐私政策合规检查通过"
        )


class TermsOfServiceRule(BaseGuardrail):
    """服务条款规则"""

    def __init__(self):
        super().__init__(
            rule_id="terms_of_service",
            name="服务条款合规检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.COMPLIANCE
        )
        # 检测违反服务条款的行为
        self.violation_patterns = [
            r"(?:商业用途|盈利|赚钱)\s*[\s\S]*?(?:使用|利用)\s*[\s\S]*?(?:本服务|本系统)",
            r"(?:反编译|逆向工程|破解)\s*[\s\S]*?(?:系统|软件|服务)",
            r"(?:复制|抄袭|盗用)\s*[\s\S]*?(?:代码|内容|创意)",
        ]
        self.violation_keywords = [
            "商业盈利",
            "反编译系统代码",
            "破解软件限制",
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

        violations = []
        for pattern in self.violation_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                violations.append(pattern)
        for keyword in self.violation_keywords:
            if keyword in input_data:
                violations.append(f"keyword:{keyword}")

        if violations:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到服务条款违规",
                details={"violations": violations},
                suggestion="请遵守服务条款，合理使用旅游规划服务"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过服务条款合规检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含合规警告
        violation_patterns = [
            r"(?:版权所有|Copyright)",
            r"(?:未经许可|禁止复制)",
            r"(?:商业用途需授权)",
        ]

        for pattern in violation_patterns:
            if re.search(pattern, output_data, re.IGNORECASE):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.LOW,
                    passed=False,
                    message="输出包含合规声明",
                    suggestion="内容已添加合规声明"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出服务条款合规检查通过"
        )
