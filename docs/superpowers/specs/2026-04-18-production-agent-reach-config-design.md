# Production Readiness And Agent-Reach Config Design

## Goal

完善当前旅行规划助手的第一批未完成生产化能力：配置从 `.env.example` 迁移为 YAML 示例，加入 Agent-Reach 各渠道 cookie/credential 占位，并让后端能根据配置选择 Mock 工具或 Agent-Reach 只读检索适配。真实 cookie 和 API key 由使用者后续在本地配置文件中补充，不提交到仓库。

## Scope

本次实现聚焦不依赖商业第三方账号即可完成的能力：

- 新增 YAML 配置模板，替代 `.env.example` 作为主要配置示例。
- 在 YAML 中预留 Agent-Reach 涉及渠道的 cookie、token、API key、超时和启用开关字段。
- `Settings` 支持从 YAML 文件读取配置，并保留环境变量覆盖能力。
- 新增工具提供者工厂，根据 `use_mock_only` 与 `enable_agent_reach` 选择 `MockProvider` 或 `AgentReachAdapter`。
- 增加生产就绪检查接口，用于检查数据库、队列、工具配置状态。
- 补充 Worker / Agent-Reach 配置说明文档。

## Out Of Scope

本次不实现真实交易、支付、账号体系、前端页面、复杂推荐排序模型，也不提交任何真实 cookie。Agent-Reach 的深度渠道自动化只做到配置和只读检索适配层，具体 cookie 值和第三方账号由部署者在本地 YAML 中填写。

## Configuration Design

新增 `config.example.yaml`，结构按模块组织：

- `app`: 应用名、版本、debug。
- `llm`: provider、model、base_url、api_key、max_tokens、temperature。
- `features`: `use_mock_only`、`enable_agent_reach`。
- `tools`: tool timeout 与 Agent-Reach 配置。
- `session`: 会话超时和历史长度。
- `database`: driver、sqlite path、database_url、mysql 连接字段。
- `redis`: redis_url。
- `tasks`: retry、lock、idempotency、recovery 参数。

Agent-Reach cookie 放在 `tools.agent_reach.channels` 下，每个渠道独立配置，例如 `xiaohongshu.cookie`、`weibo.cookie`、`twitter.cookie`、`reddit.cookie`、`bilibili.cookie`、`youtube.cookies_file`、`wechat.cookie`。字段值在模板中保持空字符串或明显占位符。

`Settings` 读取顺序：

1. 默认值。
2. YAML 配置文件，默认路径为 `config.yaml`，可通过 `APP_CONFIG_FILE` 指定。
3. 环境变量覆盖。

这样既能兼容部署平台的环境变量注入，也方便本地把大量 cookie 放进一个未提交的 YAML 文件。

## Tool Selection

新增 `app/tools/factory.py`：

- 当 `use_mock_only=True` 时，返回 `MockProvider`。
- 当 `use_mock_only=False` 且 `enable_agent_reach=True` 时，返回 `AgentReachAdapter`。
- Agent-Reach 初始化失败或配置不可用时，显式降级到 Mock，并在 ready check 中暴露降级状态。

路由初始化不再直接写死 `MockProvider()`，而是通过工厂创建工具提供者。

## Agent-Reach Adapter Boundary

`AgentReachAdapter` 保持当前 ToolInterface，不让业务 Agent 直接依赖 Agent-Reach 命令细节。第一批只读能力覆盖：

- `search_attraction`
- `rag_search`

交通和酒店查询仍走 Mock，直到接入真实交通/酒店数据源。Agent-Reach fetcher 接口负责读取 YAML 中的渠道配置，并根据可用渠道执行检索。请求超时、异常、空结果都降级到 Mock。

## Readiness Endpoint

新增 `GET /health/ready`，返回：

- `status`: `ready` 或 `degraded`
- `database`: 当前连接是否可用
- `queue`: Redis 或本地队列状态
- `tools`: 当前工具模式、Agent-Reach 是否启用、是否降级
- `config`: 关键生产配置提示，例如仍使用 SQLite、本地队列或 Mock-only

`/health` 继续只表示进程存活。

## Testing

按 TDD 增加测试：

- YAML 配置可加载，并能被环境变量覆盖。
- Agent-Reach cookie 字段能被解析但不会要求真实值。
- 工具工厂在 Mock-only、Agent-Reach enabled、Agent-Reach fallback 三种场景返回正确工具。
- `/health/ready` 能反映 SQLite/本地队列/Mock 工具的 degraded 提示。
- 现有 `/chat`、异步任务和 Worker 测试保持通过。

## Security Notes

- `config.example.yaml` 只放占位符，不包含真实 cookie。
- 新增 `.gitignore` 规则忽略 `config.yaml`、`config.local.yaml`、`*.cookies.txt` 等本地敏感文件。
- 日志和 ready check 不输出 cookie 原文，只输出是否配置。

## Rollout

第一步提交配置加载和 YAML 模板；第二步接入工具工厂；第三步增加 readiness endpoint；第四步补充文档和全量测试。每一步保持现有接口兼容。
