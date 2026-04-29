# CLAUDE.md

此文件为 Claude Code 在此项目中工作时提供指导。

## 环境配置

### Conda 环境
- **项目环境**: `leetcode`（Python 3.10.16）
- **激活命令**: `conda activate leetcode`
- **运行命令前缀**: `conda run -n leetcode <command>`
- **不要使用 base 环境**

### 已安装的核心依赖
- FastAPI 0.135.2
- SQLAlchemy 2.0.47
- Pydantic 2.12.5
- LangGraph 0.2.67
- PyMySQL 1.1.2
- Redis 7.4.0
- Uvicorn 0.41.0
- AgentReach 1.4.0

## 项目结构

```
agent/
├── app/                    # 后端应用
│   ├── api/               # API 路由
│   ├── agents/            # 多智能体系统
│   ├── config/            # 配置管理
│   ├── db/                # 数据库模型和仓库
│   ├── services/          # 业务逻辑服务
│   ├── state/             # 状态管理
│   ├── tools/             # 工具适配器
│   └── workers/           # 异步任务 worker
├── frontend/              # React 前端
├── tests/                 # 测试文件
└── config.yaml            # 应用配置
```

## 数据库

- **默认**: SQLite (`travel_planner.db`)
- **可选**: MySQL（已在 config.yaml 中配置）
- **连接**: 通过 SQLAlchemy，支持自动建表

## 常用命令

### 后端
```bash
# 激活环境
conda activate leetcode

# 启动后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
pytest tests/

# 安装依赖
pip install -r requirements.txt
```

### 前端
```bash
cd frontend
npm install
npm run dev
```
