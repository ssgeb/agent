"""
工具白名单机制
用于确保只允许使用合法的工具和功能
"""

import re
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    category: str
    description: str
    allowed_operations: List[str]
    risk_level: str = "low"


class ToolWhitelist:
    """工具白名单管理器"""

    def __init__(self):
        # 定义允许使用的工具
        self.allowed_tools = {
            # 搜索工具
            "web_search": ToolInfo(
                name="web_search",
                category="search",
                description="网络搜索",
                allowed_operations=["search", "query"],
                risk_level="low"
            ),
            "location_search": ToolInfo(
                name="location_search",
                category="travel",
                description="地点搜索",
                allowed_operations=["search", "get_details", "get_reviews"],
                risk_level="low"
            ),
            "hotel_search": ToolInfo(
                name="hotel_search",
                category="travel",
                description="酒店搜索",
                allowed_operations=["search", "check_availability", "get_prices"],
                risk_level="low"
            ),
            "transport_search": ToolInfo(
                name="transport_search",
                category="travel",
                description="交通搜索",
                allowed_operations=["search", "get_schedule", "get_fare"],
                risk_level="low"
            ),
            # 计算工具
            "calculate_budget": ToolInfo(
                name="calculate_budget",
                category="calculation",
                description="预算计算",
                allowed_operations=["calculate", "estimate"],
                risk_level="low"
            ),
            "calculate_duration": ToolInfo(
                name="calculate_duration",
                category="calculation",
                description="时长计算",
                allowed_operations=["calculate", "estimate"],
                risk_level="low"
            ),
            # 地图工具
            "get_map": ToolInfo(
                name="get_map",
                category="map",
                description="获取地图",
                allowed_operations=["get_map", "get_directions"],
                risk_level="low"
            ),
            # 翻译工具
            "translate": ToolInfo(
                name="translate",
                category="language",
                description="翻译",
                allowed_operations=["translate"],
                risk_level="low"
            ),
        }

        # 工具名称的正则表达式模式
        self.tool_patterns = {
            "web_search": r"(?:搜索|查找|search|find)[\s\S]*?(?:信息|资讯|web)",
            "location_search": r"(?:查找|搜索|search)[\s\S]*?(?:景点|地点|位置|place|location)",
            "hotel_search": r"(?:查找|搜索|search)[\s\S]*?(?:酒店|旅馆|住宿|hotel)",
            "transport_search": r"(?:查询|搜索|search)[\s\S]*?(?:交通|交通方式|交通工具|transport)",
            "calculate_budget": r"(?:计算|估算|calculate|estimate)[\s\S]*?(?:预算|费用|花费|budget)",
            "calculate_duration": r"(?:计算|估算|calculate|estimate)[\s\S]*?(?:时间|时长|duration)",
            "get_map": r"(?:查看|显示|获取|get)[\s\S]*?(?:地图|路线|map|route)",
            "translate": r"(?:翻译|translate)[\s\S]*?(?:成|为|into)[\s\S]*?(?:英文|中文|English|Chinese)",
        }

    def is_tool_allowed(self, tool_name: str, operation: str = None) -> bool:
        """检查工具是否允许使用"""
        if tool_name not in self.allowed_tools:
            return False

        tool = self.allowed_tools[tool_name]

        # 如果没有指定操作，只检查工具是否允许
        if operation is None:
            return True

        # 检查操作是否允许
        return operation in tool.allowed_operations

    def detect_tool_usage(self, input_data: str) -> List[Dict[str, Any]]:
        """检测输入中提到的工具使用"""
        detected_tools = []

        for tool_name, pattern in self.tool_patterns.items():
            if re.search(pattern, input_data, re.IGNORECASE):
                tool = self.allowed_tools[tool_name]
                detected_tools.append({
                    "tool_name": tool_name,
                    "tool_info": tool,
                    "risk_level": tool.risk_level
                })

        return detected_tools

    def get_tool_suggestions(self, input_data: str) -> List[str]:
        """获取工具使用建议"""
        suggestions = []

        # 检查是否在询问旅游规划相关
        if re.search(r"(?:旅游|旅行|计划|行程)", input_data, re.IGNORECASE):
            suggestions.extend([
                "可以使用地点搜索来查找旅游景点",
                "可以使用酒店搜索来查找住宿",
                "可以使用交通搜索来查询交通方式"
            ])

        # 检查是否在询问预算
        if re.search(r"(?:预算|费用|价格|花费)", input_data, re.IGNORECASE):
            suggestions.append("可以使用预算计算工具来估算旅行费用")

        # 检查是否在询问时间
        if re.search(r"(?:时间|时长|多久|几小时)", input_data, re.IGNORECASE):
            suggestions.append("可以使用时长计算工具来估算行程时间")

        return suggestions

    def validate_tool_operation(self, tool_name: str, operation: str) -> Dict[str, Any]:
        """验证工具操作"""
        if tool_name not in self.allowed_tools:
            return {
                "valid": False,
                "message": f"工具 '{tool_name}' 不在白名单中",
                "suggestion": "请使用合法的旅游规划工具"
            }

        tool = self.allowed_tools[tool_name]

        if operation not in tool.allowed_operations:
            return {
                "valid": False,
                "message": f"工具 '{tool_name}' 的操作 '{operation}' 不被允许",
                "allowed_operations": tool.allowed_operations,
                "suggestion": f"请使用以下允许的操作: {', '.join(tool.allowed_operations)}"
            }

        return {
            "valid": True,
            "message": "工具操作验证通过",
            "tool_info": tool
        }