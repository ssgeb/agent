# 多智能体旅行规划助手：详细设计文档

**设计日期**: 2026-04-13  
**项目名称**: 多智能体旅行规划助手  
**版本**: V1.0  
**设计者**: Claude Code  

## 1. 项目概述

### 1.1 项目定位
本项目是一个基于大模型与多智能体协同的旅行规划系统，面向用户自然语言旅行需求，支持通过多轮对话完成需求理解、任务拆解、信息检索、方案生成与持续调整，最终输出可执行的旅行方案。

### 1.2 项目目标
构建一个可扩展、可迭代、可工程化落地的多智能体旅行规划助手，具备以下核心能力：
- 支持自然语言输入旅行需求
- 支持多轮对话与状态记忆
- 能自动拆解交通、酒店、行程等任务
- 能调用工具或 MCP 服务获取外部信息
- 能生成结构化、可调整的旅行方案
- 能作为 FastAPI 后端服务独立运行
- 第一版先以 mock tools 实现最小可运行版本

## 2. 整体架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────┐
│             API 层                  │  
│  /health, /chat, /session/{id},    │
│  /plan/{id}                        │
├─────────────────────────────────────┤
│           Service 层                │
│  请求编排、状态读写、               │
│  Agent 调用衔接                    │
├─────────────────────────────────────┤
│            Agent 层                │
│  Planner (主控) +                  │
│  Transport/Hotel/Itinerary (子)   │
├─────────────────────────────────────┤
│            工具层                  │
│  统一 Tool Interface               │
│  Mock + External Adapter           │
├─────────────────────────────────────┤
│        状态与数据层                │
│  ConversationState, TripState,     │
│  CurrentPlan, StateManager         │
└─────────────────────────────────────┘
```

### 2.2 核心原则
1. **Agent 间解耦**：通过接口通信，避免直接依赖
2. **状态统一管理**：所有状态变更通过 Planner / StateManager 进行
3. **工具抽象化**：屏蔽底层实现差异，便于后续替换
4. **Mock 优先**：第一版使用模拟数据，保证核心流程跑通

## 3. 详细组件设计

### 3.1 API 层设计

#### FastAPI 接口定义
```python
# app/api/routes.py
@router.get("/health")
async def health_check() -> HealthResponse:
    """健康检查接口"""

@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """主对话接口"""
    # 自然语言输入，返回结构化响应

@router.get("/session/{id}")
async def get_session(session_id: str) -> SessionResponse:
    """获取会话状态"""

@router.get("/plan/{id}")
async def get_plan(plan_id: str) -> PlanResponse:
    """获取当前旅行方案"""
```

#### 请求/响应模型
```python
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    
class ChatResponse(BaseModel):
    response: str
    session_id: str
    updated_plan: Optional[Dict] = None
    pending_questions: Optional[List[str]] = None
```

### 3.2 Service 层设计

#### ChatService
```python
class ChatService:
    """对话流程编排服务"""
    
    async def process_message(self, request: ChatRequest) -> ChatResponse:
        # 1. 解析用户消息
        # 2. 更新会话状态
        # 3. 调用 Planner Agent
        # 4. 返回响应
```

#### SessionService
```python
class SessionService:
    """会话生命周期管理"""
    
    def create_session(self) -> str:
        """创建新会话"""
        
    def get_session(self, session_id: str) -> ConversationState:
        """获取会话状态"""
        
    def cleanup_expired_sessions(self):
        """清理过期会话"""
```

#### StateService
```python
class StateService:
    """状态读写协调"""
    
    async def update_trip_state(self, session_id: str, updates: Dict):
        """更新旅行状态"""
        
    async def get_current_plan(self, session_id: str) -> CurrentPlan:
        """获取当前方案"""
```

### 3.3 Agent 层设计

#### Planner Agent（主控）
```python
class PlannerAgent:
    """主控 Agent，负责任务路由与状态管理"""
    
    async def process(self, message: str, state: ConversationState) -> PlannerResponse:
        # 1. 理解用户意图
        # 2. 提取结构化信息
        # 3. 更新 TripState
        # 4. 路由到子 Agent
        # 5. 汇总结果
        # 6. 生成响应
```

#### 子 Agent 基类
```python
class BaseAgent(ABC):
    """子 Agent 基类"""
    
    @abstractmethod
    async def process(self, request: AgentRequest, state: TripState) -> AgentResponse:
        """处理请求"""
        
    @abstractmethod
    def can_handle(self, intent: str) -> bool:
        """判断是否能处理"""
```

#### Transport Agent
```python
class TransportAgent(BaseAgent):
    """交通方案查询与推荐"""
    
    async def process(self, request: TransportRequest, state: TripState) -> TransportResponse:
        # 1. 识别交通需求
        # 2. 调用工具查询方案
        # 3. 根据条件筛选
        # 4. 返回推荐方案
```

#### Hotel Agent
```python
class HotelAgent(BaseAgent):
    """酒店查询与推荐"""
    
    async def process(self, request: HotelRequest, state: TripState) -> HotelResponse:
        # 1. 识别住宿需求
        # 2. 调用工具查询酒店
        # 3. 基于预算评分筛选
        # 4. 返回推荐结果
```

#### Itinerary Agent
```python
class ItineraryAgent(BaseAgent):
    """行程规划与景点推荐"""
    
    async def process(self, request: ItineraryRequest, state: TripState) -> ItineraryResponse:
        # 1. 检索景点信息
        # 2. 生成每日行程
        # 3. 优化路线顺序
        # 4. 返回行程方案
```

### 3.4 工具层设计

#### 统一工具接口
```python
class ToolInterface:
    """统一工具调用接口"""
    
    @abstractmethod
    async def search_transport(self, params: TransportParams) -> List[TransportOption]:
        """搜索交通方案"""
        
    @abstractmethod
    async def search_hotel(self, params: HotelParams) -> List[HotelOption]:
        """搜索酒店"""
        
    @abstractmethod
    async def search_attraction(self, params: AttractionParams) -> List[AttractionOption]:
        """搜索景点"""
        
    @abstractmethod
    async def rag_search(self, query: str) -> List[Document]:
        """RAG 检索"""
```

#### Mock Provider
```python
class MockProvider(ToolInterface):
    """模拟数据提供者"""
    
    # 交通 Mock 数据
    TRANSPORT_MOCK_DATA = {
        "flight_options": [...],
        "train_options": [...],
        "bus_options": [...]
    }
    
    # 酒店 Mock 数据
    HOTEL_MOCK_DATA = {
        "hotel_options": [...]
    }
    
    # 景点 Mock 数据  
    ATTRACTION_MOCK_DATA = {
        "attraction_options": [...]
    }
```

#### External Adapter（Agent-Reach 集成）
```python
class AgentReachAdapter(ToolInterface):
    """Agent-Reach 外部服务适配器"""
    
    async def search_transport(self, params: TransportParams) -> List[TransportOption]:
        # 调用 Agent-Reach 交通搜索
        pass
        
    async def rag_search(self, query: str) -> List[Document]:
        # 调用 Agent-Reach 搜索能力
        pass
```

### 3.5 状态与数据层设计

#### ConversationState
```python
class ConversationState(BaseModel):
    """对话上下文状态"""
    
    session_id: str
    message_history: List[Message]
    summary: Optional[str] = None
    current_intent: Optional[str] = None
    active_agent: Optional[str] = None
    pending_questions: List[str] = []
    tool_results: Dict[str, Any] = {}
    last_plan: Optional[Dict] = None
    final_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

#### TripState
```python
class TripState(BaseModel):
    """结构化旅行信息"""
    
    # 基本信息
    origin: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[int] = None
    
    # 人员信息
    travelers_count: Optional[int] = 1
    traveler_type: Optional[str] = "adult"
    
    # 偏好设置
    budget: Optional[Dict[str, float]] = None
    transport_preferences: Dict[str, Any] = {}
    hotel_preferences: Dict[str, Any] = {}
    attraction_preferences: Dict[str, Any] = {}
    pace_preference: Optional[str] = "moderate"
    
    # 其他
    must_visit_places: List[str] = []
    excluded_places: List[str] = []
    notes: List[str] = []
```

#### CurrentPlan
```python
class CurrentPlan(BaseModel):
    """当前旅行方案"""
    
    plan_id: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    
    # 方案内容
    transport_plan: Optional[TransportPlan] = None
    hotel_plan: Optional[HotelPlan] = None
    itinerary_plan: Optional[ItineraryPlan] = None
    
    # 预算估算
    total_estimate: Dict[str, float] = {}
```

#### StateManager
```python
class StateManager:
    """状态管理器"""
    
    def __init__(self):
        self.conversation_states: Dict[str, ConversationState] = {}
        self.trip_states: Dict[str, TripState] = {}
        self.current_plans: Dict[str, CurrentPlan] = {}
    
    async def update_conversation_state(self, session_id: str, updates: Dict):
        """更新对话状态"""
        
    async def update_trip_state(self, session_id: str, updates: Dict):
        """更新旅行状态"""
        
    async def save_plan(self, session_id: str, plan: CurrentPlan):
        """保存方案"""
```

## 4. 数据流设计

### 4.1 主流程
```
用户输入 → FastAPI (/chat) → 
ChatService → PlannerAgent → 
解析意图 → 更新状态 → 
路由到子Agent → 
并行调用工具 → 
汇总结果 → 更新方案 → 
返回响应
```

### 4.2 子 Agent 调用流程
```
PlannerAgent
    ↓
判断意图 (transport/hotel/itinerary)
    ↓
选择相应子Agent
    ↓
构造 AgentRequest
    ↓
子Agent.process()
    ↓
调用 ToolInterface
    ↓
返回 AgentResponse
    ↓
Planner汇总所有响应
```

### 4.3 状态更新流程
```
用户输入 → Planner解析 → 
判断需要更新字段 → 
调用 StateManager.update_trip_state → 
更新 TripState → 
子Agent读取最新状态 → 
继续处理 → 
生成方案 → 
保存到 CurrentPlan
```

## 5. 错误处理设计

### 5.1 错误类型
```python
class TravelPlannerError(Exception):
    """基础错误类"""
    
class IntentError(TravelPlannerError):
    """意图识别错误"""
    
class ToolCallError(TravelPlannerError):
    """工具调用错误"""
    
class StateError(TravelPlannerError):
    """状态管理错误"""
```

### 5.2 异常处理策略
1. **工具调用失败**：返回错误信息，使用 mock 数据兜底
2. **状态异常**：记录错误日志，尝试恢复或提示用户重新开始
3. **Agent处理失败**：降级处理，保证核心流程可用
4. **超时处理**：设置合理超时时间，避免长时间等待

## 6. 配置设计

### 6.1 环境配置
```python
# .env
APP_NAME=travel-planner
APP_VERSION=1.0.0
DEBUG=true

# Agent配置
LLM_MODEL=gpt-3.5-turbo
MAX_TOKENS=1000
TEMPERATURE=0.7

# 工具配置
USE_MOCK_ONLY=true
ENABLE_AGENT_REACH=false
TOOL_TIMEOUT=30

# 会话配置
SESSION_TIMEOUT=3600
MAX_HISTORY_LENGTH=50
```

### 6.2 工具配置
```yaml
# config/tools.yaml
transport:
  mock:
    enabled: true
    providers:
      - flight
      - train
      - bus
      
hotel:
  mock:
    enabled: true
    providers:
      - booking
      - ctrip
      
itinerary:
  mock:
    enabled: true
    providers:
      - attraction
      - activity
```

## 7. 测试策略

### 7.1 单元测试
- Agent 处理逻辑测试
- 状态管理测试
- 工具接口测试
- Mock 数据测试

### 7.2 集成测试
- 端到端对话流程测试
- 多 Agent 协作测试
- 状态持久化测试

### 7.3 测试用例示例
```python
# test_planner_agent.py
async def test_transport_intent():
    """测试交通意图识别"""
    
async def test_multi_agent_coordination():
    """测试多 Agent 协作"""
```

## 8. 第一版 MVP 范围

### 8.1 V1 必做
- [x] FastAPI 项目骨架
- [x] `/health` 与 `/chat` 接口
- [x] Planner Agent 基础逻辑
- [ ] Transport Agent（mock 实现）
- [ ] Hotel Agent（mock 实现）
- [ ] Itinerary Agent（mock 实现）
- [ ] ConversationState 与 TripState
- [ ] 基础工具接口
- [ ] Agent-Reach 工具适配接口占位
- [ ] 日志与配置管理
- [ ] README 与启动说明

### 8.2 V1 暂不做
- [ ] 前端页面
- [ ] 真实第三方平台深度接入
- [ ] Agent-Reach 真实渠道的完整配置与自动化调用
- [ ] 长期用户偏好记忆
- [ ] 复杂推荐排序模型
- [ ] 完整权限系统
- [ ] 复杂监控与分析后台

## 9. 开发顺序

1. 搭建项目骨架
2. 定义 schema 与状态模型
3. 实现 Planner Agent 基础逻辑
4. 实现三个子 Agent 骨架
5. 实现统一 tool interface 与 mock tools
6. 打通 Planner -> 子 Agent -> 汇总输出调用链
7. 增加基础 RAG 检索
8. 增加 Agent-Reach 工具适配接口占位
9. 补充日志、异常处理、README
10. 最后再考虑真实 API / MCP / Agent-Reach 渠道对接

## 10. 扩展设计

### 10.1 未来扩展点
1. **真实数据源集成**：携程、飞猪、美团等
2. **推荐算法优化**：基于用户偏好的智能推荐
3. **多模态支持**：图片识别景点、语音输入等
4. **社交功能**：分享方案、多人协作规划

### 10.2 架构扩展点
1. **插件化工具系统**：支持动态加载新工具
2. **分布式部署**：支持多实例部署
3. **缓存层**：Redis 缓存常用查询结果
4. **消息队列**：处理高并发请求

---

**设计文档完成**  
**文档路径**: `docs/superpowers/specs/2026-04-13-multi-agent-travel-planner-design.md`  
**下一步**: 等待用户确认设计，进入实现计划阶段