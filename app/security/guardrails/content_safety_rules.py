"""
内容安全防护规则
"""

import re
from typing import Dict, List, Optional, Any
from .base import BaseGuardrail, RuleResult, RuleSeverity, RuleCategory


class InappropriateContentRule(BaseGuardrail):
    """不当内容规则"""

    def __init__(self):
        super().__init__(
            rule_id="inappropriate_content",
            name="不当内容检测",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.CONTENT_SAFETY
        )
        # 检测不当内容
        self.inappropriate_patterns = [
            # 暴力威胁
            r"(?:伤害|攻击|暴力|恐吓|威胁)\s*[\s\S]*?(?:他人|别人|用户)",
            # 非法活动
            r"(?:违法|非法|犯罪|走私|贩毒)\s*[\s\S]*?(?:行为|活动|操作)",
            # 不道德内容
            r"(?:色情| porn|sex|成人|淫秽|色情)\s*[\s\S]*?(?:内容|信息|图片)",
            # 歧视性内容
            r"(?:歧视|偏见|种族|性别|宗教)\s*[\s\S]*?(?:歧视|偏见|攻击)",
        ]
        self.inappropriate_keywords = [
            "暴力恐怖",
            "色情内容",
            "攻击某个网站",
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
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                matches.append(pattern)
        for keyword in self.inappropriate_keywords:
            if keyword in input_data:
                matches.append(f"keyword:{keyword}")

        if matches:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到不当内容",
                details={"matched_patterns": matches},
                suggestion="请使用文明的语言描述您的旅游需求"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过不当内容检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含不当内容
        inappropriate_patterns = [
            r"(?:暴力|攻击|伤害|恐吓)",
            r"(?:违法|犯罪|非法)",
            r"(?:色情|淫秽|成人)",
            r"(?:歧视|偏见|仇恨)",
        ]

        for pattern in inappropriate_patterns:
            if re.search(pattern, output_data, re.IGNORECASE):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.HIGH,
                    passed=False,
                    message="输出包含不当内容",
                    suggestion="内容已被安全过滤"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出不当内容检查通过"
        )


class SafeSearchRule(BaseGuardrail):
    """安全搜索规则"""

    def __init__(self):
        super().__init__(
            rule_id="safe_search",
            name="安全搜索检测",
            severity=RuleSeverity.MEDIUM,
            category=RuleCategory.CONTENT_SAFETY
        )
        # 检测安全搜索绕过
        self.bypass_patterns = [
            r"(?:绕过|忽略|关闭|禁用)\s*[\s\S]*?(?:安全搜索|内容过滤|安全模式)",
            r"(?:显示|查看)\s*[\s\S]*?(?:未过滤|原始|全部|所有)\s*[\s\S]*?(?:结果|内容)",
            r"(?:不检查|不过滤)\s*[\s\S]*?(?:安全性|适当性|合规性)",
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

        bypass_detected = False
        for pattern in self.bypass_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                bypass_detected = True
                break

        if bypass_detected:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                passed=False,
                message="检测到尝试绕过安全搜索",
                suggestion="安全搜索功能已开启，保护用户免受不当内容"
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            passed=True,
            message="通过安全搜索检测"
        )

    def check_output(self, output_data: str, input_data: str, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        # 检查输出是否包含被过滤的内容
        filtered_patterns = [
            r"\[已过滤\]",
            r"\[内容隐藏\]",
            r"\[安全拦截\]",
        ]

        for pattern in filtered_patterns:
            if re.search(pattern, output_data):
                return RuleResult(
                    rule_id=f"{self.rule_id}_output",
                    rule_name=f"{self.name}_output",
                    category=self.category,
                    severity=RuleSeverity.MEDIUM,
                    passed=False,
                    message="输出包含过滤内容标识",
                    suggestion="内容已安全过滤"
                )

        return RuleResult(
            rule_id=f"{self.rule_id}_output",
            rule_name=f"{self.name}_output",
            category=self.category,
            severity=self.severity,
            passed=True,
            message="输出安全搜索检查通过"
        )
