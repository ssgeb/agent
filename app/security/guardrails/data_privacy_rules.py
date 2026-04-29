"""
数据隐私防护规则
"""

import re
from typing import Dict, List, Optional, Any
from .base import BaseGuardrail, RuleResult, RuleSeverity, RuleCategory


class PersonalDataRequestRule(BaseGuardrail):
    """个人数据请求规则"""

    def __init__(self):
        super().__init__(
            rule_id="personal_data_request",
            name="个人数据请求检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.DATA_PRIVACY
        )
        # 检测尝试获取个人数据
        self.personal_data_patterns = [
            r"(?:获取|查询|查看)\s*[\s\S]*?(?:用户数据|个人信息|隐私数据|敏感信息)",
            r"(?:下载|导出|复制)\s*[\s\S]*?(?:数据库|文件|记录)",
            r"(?:所有|全部|每个)\s*[\s\S]*?(?:用户|客户|会员)\s*[\s\S]*?(?:信息|数据|资料)",
            r"(?:未经过滤|原始|完整)\s*[\s\S]*?(?:数据|信息|记录)",
            r"(?:身份证|护照|驾驶证)\s*[\s\S]*?(?:号码|号|号吗)",
            r"(?:手机|电话)\s*[\s\S]*?(?:号码|号|号吗|号码段)",
            r"(?:银行卡|信用卡)\s*[\s\S]*?(?:号码|号|号吗|密码)",
            r"(?:住址|家庭|婚姻)\s*[\s\S]*?(?:信息|情况|状况)",
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
        for pattern in self.personal_data_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                matches.append(pattern)

        if matches:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到尝试获取个人数据",
                details={"matched_patterns": matches},
                suggestion="我们保护用户隐私，无法提供个人数据"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过个人数据请求检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含个人数据
        personal_data_patterns = [
            r"用户数据|个人信息|隐私数据",
            r"数据库记录|用户记录",
            r"全部用户|所有用户|每个用户",
        ]

        for pattern in personal_data_patterns:
            if re.search(pattern, output_data, re.IGNORECASE):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.HIGH,
                    passed=False,
                    message="输出可能包含个人数据",
                    suggestion="输出内容已被安全过滤"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出个人数据检查通过"
        )


class SensitiveInfoLeakRule(BaseGuardrail):
    """敏感信息泄露规则"""

    def __init__(self):
        super().__init__(
            rule_id="sensitive_info_leak",
            name="敏感信息泄露检测",
            severity=RuleSeverity.CRITICAL,
            category=RuleCategory.DATA_PRIVACY
        )
        # 检测敏感信息模式
        self.sensitive_patterns = [
            # 身份证号
            r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]",
            # 手机号
            r"1[3-9]\d{9}",
            # 邮箱
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            # 信用卡号
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            # 密码相关
            r"(?:密码|口令|pwd|pass)[\s:：]*[\w\d!@#$%^&*]{6,}",
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

        sensitive_info = []
        for pattern in self.sensitive_patterns:
            matches = re.findall(pattern, input_data, re.IGNORECASE)
            if matches:
                sensitive_info.extend(matches[:3])  # 最多显示3个匹配

        if sensitive_info:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到敏感信息",
                details={"sensitive_info": sensitive_info},
                suggestion="请不要在对话中包含个人敏感信息"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过敏感信息泄露检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        sensitive_matches = []
        for pattern in self.sensitive_patterns:
            matches = re.findall(pattern, output_data, re.IGNORECASE)
            if matches:
                sensitive_matches.extend(matches)

        if sensitive_matches:
            return RuleResult(
                rule_id=f"{self.rule_id}_output",
                rule_name=f"{self.name}_output",
                category=self.category,
                severity=RuleSeverity.HIGH,
                passed=False,
                message="输出包含敏感信息，已被自动过滤",
                details={"filtered_count": len(sensitive_matches)},
                suggestion="敏感信息已被安全处理"
            )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出敏感信息检查通过"
        )