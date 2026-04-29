"""
Guardrails 基础规则类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import re
from dataclasses import dataclass


class RuleSeverity(Enum):
    """规则严重程度"""
    LOW = "low"          # 警告，可继续
    MEDIUM = "medium"    # 风险，建议阻止
    HIGH = "high"        # 危险，必须阻止
    CRITICAL = "critical"  # 严重，立即阻断

    @property
    def priority(self) -> int:
        """严重程度的数值优先级，用于正确比较"""
        return {
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3,
        }[self.value]


class RuleCategory(Enum):
    """规则类别"""
    PROMPT_INJECTION = "prompt_injection"
    OUTPUT_LEAKAGE = "output_leakage"
    TOOL_ABUSE = "tool_abuse"
    DATA_PRIVACY = "data_privacy"
    CONTENT_SAFETY = "content_safety"
    COMPLIANCE = "compliance"


@dataclass
class RuleResult:
    """规则检查结果"""
    rule_id: str
    rule_name: str
    category: RuleCategory
    severity: RuleSeverity
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None


class BaseGuardrail(ABC):
    """Guardrails 基础规则类"""

    def __init__(self, rule_id: str, name: str, severity: RuleSeverity, category: RuleCategory):
        self.rule_id = rule_id
        self.name = name
        self.severity = severity
        self.category = category

    @abstractmethod
    def check(self, input_data: Any, context: Optional[Dict] = None) -> RuleResult:
        """检查输入数据"""
        pass

    @abstractmethod
    def check_output(self, output_data: Any, input_data: Any, context: Optional[Dict] = None) -> RuleResult:
        """检查输出数据"""
        pass


class GuardrailsEngine:
    """Guardrails 引擎"""

    def __init__(self):
        self.rules: List[BaseGuardrail] = []

    def add_rule(self, rule: BaseGuardrail):
        """添加规则"""
        self.rules.append(rule)

    def add_rules(self, rules: List[BaseGuardrail]):
        """批量添加规则"""
        self.rules.extend(rules)

    def check_input(self, input_data: Any, context: Optional[Dict] = None) -> List[RuleResult]:
        """检查所有规则对输入的验证"""
        results = []
        for rule in self.rules:
            result = rule.check(input_data, context)
            results.append(result)
        return results

    def check_output(self, output_data: Any, input_data: Any, context: Optional[Dict] = None) -> List[RuleResult]:
        """检查所有规则对输出的验证"""
        results = []
        for rule in self.rules:
            result = rule.check_output(output_data, input_data, context)
            results.append(result)
        return results

    def get_failed_rules(self, results: List[RuleResult], min_severity: RuleSeverity = RuleSeverity.MEDIUM) -> List[RuleResult]:
        """获取未通过的规则（不低于指定严重性阈值）"""
        return [
            r for r in results
            if not r.passed and r.severity.priority >= min_severity.priority
        ]

    def should_block(self, results: List[RuleResult], blocking_threshold: RuleSeverity = RuleSeverity.HIGH) -> bool:
        """判断是否应该阻断"""
        for rule in results:
            if not rule.passed and rule.severity.priority >= blocking_threshold.priority:
                return True
        return False