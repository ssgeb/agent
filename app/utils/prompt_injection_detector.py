"""
提示词注入检测器

用于检测和防止用户输入中的提示词注入攻击
"""

import re
from typing import List, Dict, Set, Tuple
from enum import Enum


class InjectionSeverity(Enum):
    """注入攻击严重程度"""
    LOW = "low"          # 可能的误报
    MEDIUM = "medium"    # 需要警告
    HIGH = "high"        # 明确的注入攻击


class InjectionPattern:
    """注入攻击模式"""

    def __init__(
        self,
        name: str,
        patterns: List[str],
        severity: InjectionSeverity,
        description: str,
        category: str
    ):
        self.name = name
        self.patterns = patterns
        self.severity = severity
        self.description = description
        self.category = category


class PromptInjectionDetector:
    """提示词注入检测器"""

    def __init__(self):
        self._load_patterns()

    def _load_patterns(self):
        """加载注入攻击模式"""
        self.patterns = [
            # 系统指令绕过
            InjectionPattern(
                name="system_override",
                patterns=[
                    r"你是\s*[\s\S]*?(?:助手|AI)",
                    r"(?:忽略|忘记)\s*[\s\S]*?之前的",
                    r"(?:不要|别要)\s*[\s\S]*?(?:过滤|审查)"
                ],
                severity=InjectionSeverity.HIGH,
                description="尝试绕过系统身份",
                category="bypass"
            ),

            # 角色扮演
            InjectionPattern(
                name="role_play",
                patterns=[
                    r"(?:扮演|假装)\s*[\s\S]*?(?:管理员|root|admin|超级用户|黑客|攻击者)",
                    r"(?:你\s*[\s\S]*?是|你现在是)\s*[\s\S]*?(?:系统|程序|AI|开发者|工程师)"
                ],
                severity=InjectionSeverity.MEDIUM,
                description="强制角色扮演",
                category="roleplay"
            ),

            # 指令注入
            InjectionPattern(
                name="instruction_injection",
                patterns=[
                    r"(?:输出|显示|打印|返回)\s*[\s\S]*?[\u4e00-\u9fff]",
                    r"(?:用\s*[\s\S]*?格式)",
                    r"(?:按照\s*[\s\S]*?方式)",
                    r"(?:遵循\s*[\s\S]*?规则)"
                ],
                severity=InjectionSeverity.MEDIUM,
                description="注入输出指令",
                category="instruction"
            ),

            # 信息泄露
            InjectionPattern(
                name="information_extraction",
                patterns=[
                    r"(?:告诉我|显示|提供)\s*[\s\S]*?(?:原始|完整|未经过滤|未审查)",
                    r"(?:不要\s*[\s\S]*?过滤)",
                    r"(?:忽略\s*[\s\S]*?安全)",
                    r"(?:绕过\s*[\s\S]*?检查)"
                ],
                severity=InjectionSeverity.HIGH,
                description="尝试获取未过滤信息",
                category="extract"
            ),

            # 代码注入
            InjectionPattern(
                name="code_injection",
                patterns=[
                    r"```[\s\S]*?```",
                    r"`[\s\S]*?`",
                    r"(?:代码|脚本|程序)\s*[\s\S]*?:",
                    r"(?:执行|运行)\s*[\s\S]*?命令"
                ],
                severity=InjectionSeverity.MEDIUM,
                description="尝试注入代码",
                category="code"
            ),

            # 提示词构造
            InjectionPattern(
                name="prompt_construction",
                patterns=[
                    r"(?:构建|构造|制作)\s*[\s\S]*?(?:提示词|prompt)",
                    r"(?:用\s*[\s\S]*?以下\s*[\s\S]*?提示词)",
                    r"SYSTEM\s*[\s\S]*?:"
                ],
                severity=InjectionSeverity.MEDIUM,
                description="构造提示词",
                category="construction"
            ),

            # 多轮指令
            InjectionPattern(
                name="multi_turn_instruction",
                patterns=[
                    r"(?:第一步|第二步|第三步|最后一步)\s*[\s\S]*?是",
                    r"(?:首先|然后|最后)\s*[\s\S]*?你要",
                    r"接下来\s*[\s\S]*?你应该",
                    r"之后\s*[\s\S]*?记住"
                ],
                severity=InjectionSeverity.MEDIUM,
                description="多轮指令注入",
                category="multiturn"
            ),

            # 压迫性指令
            InjectionPattern(
                name="pressure_tactic",
                patterns=[
                    r"(?:必须|一定|务必|只能)\s*[\s\S]*?",
                    r"(?:重要|紧急|立即|马上)\s*[\s\S]*?是",
                    r"(?:否则\s*[\s\S]*?后果)",
                    r"(?:警告\s*[\s\S]*?:)"
                ],
                severity=InjectionSeverity.LOW,
                description="使用压迫性语言",
                category="pressure"
            )
        ]

        # 构建正则表达式
        self.compiled_patterns = []
        for pattern in self.patterns:
            compiled = [re.compile(p, re.IGNORECASE) for p in pattern.patterns]
            self.compiled_patterns.append((pattern, compiled))

    def detect(self, text: str) -> List[Dict]:
        """
        检测文本中的注入攻击

        Args:
            text: 待检测的文本

        Returns:
            检测结果列表，每个结果包含：
            - pattern_name: 模式名称
            - category: 类别
            - severity: 严重程度
            - description: 描述
            - matches: 匹配内容
            - start_index: 起始位置
            - end_index: 结束位置
        """
        results = []

        for pattern, compiled_list in self.compiled_patterns:
            for compiled in compiled_list:
                for match in compiled.finditer(text):
                    result = {
                        "pattern_name": pattern.name,
                        "category": pattern.category,
                        "severity": pattern.severity.value,
                        "description": pattern.description,
                        "matches": match.group(),
                        "start_index": match.start(),
                        "end_index": match.end(),
                    }
                    results.append(result)

        return results

    def analyze(self, text: str) -> Dict:
        """
        分析文本的注入风险

        Args:
            text: 待分析的文本

        Returns:
            分析结果：
            - risk_level: 风险等级 (low/medium/high/critical)
            - detected_patterns: 检测到的模式数量
            - suspicious_patterns: 可疑模式列表
            - recommendations: 建议
        """
        results = self.detect(text)

        if not results:
            return {
                "risk_level": "low",
                "detected_patterns": 0,
                "suspicious_patterns": [],
                "recommendations": ["输入正常，可以继续处理"]
            }

        # 按严重程度分组
        high_severity = [r for r in results if r["severity"] == "high"]
        medium_severity = [r for r in results if r["severity"] == "medium"]
        low_severity = [r for r in results if r["severity"] == "low"]

        # 简化风险等级计算 - 直接基于最高严重性
        if high_severity:
            risk_level = "high"
        elif medium_severity:
            risk_level = "medium"
        else:
            risk_level = "low"

        # 生成建议
        recommendations = []

        if high_severity:
            recommendations.append("检测到高风险注入攻击，建议拒绝该请求")

        if medium_severity:
            recommendations.append("检测到中等风险注入尝试，建议审查内容")

        if len(results) > 10:
            recommendations.append("检测到大量注入模式，可能是恶意输入")

        recommendations.append("建议进行内容过滤或提示重写")

        return {
            "risk_level": risk_level,
            "detected_patterns": len(results),
            "suspicious_patterns": results[:5],  # 返回前5个最可疑的
            "recommendations": recommendations,
            "details": results
        }

    def sanitize(self, text: str, method: str = "filter") -> str:
        """
        清理文本中的注入攻击

        Args:
            text: 待清理的文本
            method: 清理方法
                - "filter": 过滤掉注入内容
                - "replace": 替换注入内容
                - "mask": 遮盖注入内容

        Returns:
            清理后的文本
        """
        if method == "filter":
            # 过滤模式：删除注入内容
            for pattern, compiled_list in self.compiled_patterns:
                for compiled in compiled_list:
                    text = compiled.sub("", text)

        elif method == "replace":
            # 替换模式：用[内容已过滤]替换
            for pattern, compiled_list in self.compiled_patterns:
                for compiled in compiled_list:
                    text = compiled.sub("[内容已过滤]", text)

        elif method == "mask":
            # 遮盖模式：用***替换
            for pattern, compiled_list in self.compiled_patterns:
                for compiled in compiled_list:
                    text = compiled.sub("***", text)

        return text.strip()

    def is_safe(self, text: str, threshold: str = "medium") -> bool:
        """
        检查文本是否安全

        Args:
            text: 待检查的文本
            threshold: 安全阈值 (low/medium/high)

        Returns:
            是否安全
        """
        analysis = self.analyze(text)
        risk_level = analysis["risk_level"]

        if threshold == "low":
            return risk_level == "low"
        elif threshold == "medium":
            return risk_level in ["low", "medium"]
        else:  # high
            return risk_level in ["low", "medium", "high"]


# 全局实例
injection_detector = PromptInjectionDetector()


def detect_prompt_injection(text: str) -> Dict:
    """检测提示词注入的便捷函数"""
    return injection_detector.analyze(text)


def sanitize_prompt(text: str) -> str:
    """清理提示词的便捷函数"""
    return injection_detector.sanitize(text, method="filter")