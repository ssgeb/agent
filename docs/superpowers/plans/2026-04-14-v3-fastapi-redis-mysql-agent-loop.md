# V3 FastAPI Redis MySQL Agent Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 FastAPI + Redis + MySQL + LangGraph 构建可恢复的异步多 Agent 对话闭环，支持多会话并发、任务状态恢复与执行结果回填。

**Architecture:** API 仅负责任务创建与查询；Redis 承担队列和运行态缓存；MySQL 作为权威持久层；Worker 驱动 StateGraph 执行并将节点结果增量回填至任务步骤与方案快照。通过 `task_id` 贯穿链路实现可追踪、可恢复、可重试。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2.x、redis-py、pytest、pytest-asyncio、httpx

---

## 文件结构与职责（V3）

- `app/db/models.py`：MySQL ORM 模型（sessions/tasks/task_steps/plan_snapshots）。
- `app/db/repository.py`：数据库读写仓储封装。
- `app/queue/redis_queue.py`：Redis 入队/出队与幂等键、锁封装。
- `app/workers/task_worker.py`：异步任务消费者与状态推进。
- `app/orchestration/stategraph_runner.py`：LangGraph 执行入口与节点回填钩子。
- `app/services/task_service.py`：任务创建、查询、状态转换服务。
- `app/api/routes.py`：新增 `/task/{task_id}`、`/plan/{session_id}/history`。
- `app/state/manager.py`：与持久层协作，支持恢复加载。
- `app/config/settings.py`：新增 Redis/MySQL 配置。
- `tests/test_task_api.py`：任务接口测试。
- `tests/test_persistence_repository.py`：持久层测试。
- `tests/test_worker_recovery.py`：恢复流程测试。

### Task 1: 数据库模型与仓储层

**Files:**
- Create: `app/db/models.py`
- Create: `app/db/repository.py`
- Create: `app/db/__init__.py`
- Create: `tests/test_persistence_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_persistence_repository.py
from app.db.repository import TaskRepository


def test_create_task_and_append_step(sqlite_repo: TaskRepository):
    task_id = sqlite_repo.create_task(session_id="s-001", task_type="chat")
    sqlite_repo.append_task_step(task_id, agent_name="planner", step_status="SUCCEEDED", output_json={"ok": True})

    task = sqlite_repo.get_task(task_id)
    steps = sqlite_repo.get_task_steps(task_id)

    assert task.status == "PENDING"
    assert len(steps) == 1
    assert steps[0].agent_name == "planner"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_persistence_repository.py::test_create_task_and_append_step -v`
Expected: FAIL with `ModuleNotFoundError` for `app.db`

- [ ] **Step 3: Write minimal implementation**

```python
# app/db/models.py
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"t-{uuid4().hex[:12]}")
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    task_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"ts-{uuid4().hex[:12]}")
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    step_status: Mapped[str] = mapped_column(String(32))
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

```python
# app/db/repository.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Task, TaskStep


class TaskRepository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(self.engine)

    def create_task(self, session_id: str, task_type: str) -> str:
        with self._session_factory() as db:
            task = Task(session_id=session_id, task_type=task_type)
            db.add(task)
            db.commit()
            db.refresh(task)
            return task.task_id

    def append_task_step(self, task_id: str, agent_name: str, step_status: str, output_json: dict) -> None:
        with self._session_factory() as db:
            db.add(TaskStep(task_id=task_id, agent_name=agent_name, step_status=step_status, output_json=output_json))
            task = db.get(Task, task_id)
            if task is not None:
                task.updated_at = datetime.utcnow()
            db.commit()

    def get_task(self, task_id: str) -> Task:
        with self._session_factory() as db:
            task = db.get(Task, task_id)
            assert task is not None
            return task

    def get_task_steps(self, task_id: str) -> list[TaskStep]:
        with self._session_factory() as db:
            return list(db.scalars(select(TaskStep).where(TaskStep.task_id == task_id)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_persistence_repository.py::test_create_task_and_append_step -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db tests/test_persistence_repository.py
git commit -m "feat: add MySQL task models and repository"
```

### Task 2: Redis 队列与任务服务

**Files:**
- Create: `app/queue/redis_queue.py`
- Create: `app/services/task_service.py`
- Modify: `app/services/__init__.py`
- Create: `tests/test_task_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_chat_returns_task_id_for_async_flow():
    client = TestClient(app)
    response = client.post("/chat", json={"message": "帮我规划杭州两日游"})

    assert response.status_code == 202
    assert response.json()["task_id"]
    assert response.json()["status"] == "PENDING"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_api.py::test_chat_returns_task_id_for_async_flow -v`
Expected: FAIL with status mismatch

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/task_service.py
class TaskService:
    def __init__(self, repository, queue) -> None:
        self.repository = repository
        self.queue = queue

    def create_chat_task(self, session_id: str, message: str) -> dict:
        task_id = self.repository.create_task(session_id=session_id, task_type="chat")
        self.queue.enqueue({"task_id": task_id, "session_id": session_id, "message": message})
        return {"task_id": task_id, "status": "PENDING"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_api.py::test_chat_returns_task_id_for_async_flow -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/queue app/services/task_service.py app/services/__init__.py tests/test_task_api.py
git commit -m "feat: add redis queue wrapper and task creation service"
```

### Task 3: Worker 与 StateGraph 执行回填

**Files:**
- Create: `app/orchestration/stategraph_runner.py`
- Create: `app/workers/task_worker.py`
- Create: `tests/test_worker_recovery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worker_recovery.py
from app.workers.task_worker import TaskWorker


def test_worker_updates_task_and_steps_on_success(fake_worker_deps):
    worker = TaskWorker(**fake_worker_deps)
    worker.process_one({"task_id": "t-001", "session_id": "s-001", "message": "查杭州酒店"})

    task = fake_worker_deps["repository"].get_task("t-001")
    steps = fake_worker_deps["repository"].get_task_steps("t-001")

    assert task.status == "SUCCEEDED"
    assert len(steps) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker_recovery.py::test_worker_updates_task_and_steps_on_success -v`
Expected: FAIL with import or missing method

- [ ] **Step 3: Write minimal implementation**

```python
# app/workers/task_worker.py
class TaskWorker:
    def __init__(self, repository, runner) -> None:
        self.repository = repository
        self.runner = runner

    def process_one(self, payload: dict) -> None:
        task_id = payload["task_id"]
        self.repository.update_task_status(task_id, "RUNNING")
        result = self.runner.run(payload)
        self.repository.append_task_step(task_id, "planner", "SUCCEEDED", result)
        self.repository.update_task_status(task_id, "SUCCEEDED")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worker_recovery.py::test_worker_updates_task_and_steps_on_success -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/orchestration app/workers tests/test_worker_recovery.py
git commit -m "feat: add worker loop and stategraph result backfill"
```

### Task 4: 查询接口与历史接口

**Files:**
- Modify: `app/api/schemas.py`
- Modify: `app/api/routes.py`
- Modify: `app/services/state_service.py`
- Modify: `tests/test_session_plan_api.py`
- Modify: `tests/test_task_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_task_query_endpoint_returns_status():
    client = TestClient(app)
    task_id = client.post("/chat", json={"message": "查杭州酒店"}).json()["task_id"]

    response = client.get(f"/task/{task_id}")

    assert response.status_code == 200
    assert response.json()["task_id"] == task_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_api.py::test_task_query_endpoint_returns_status -v`
Expected: FAIL with 404

- [ ] **Step 3: Write minimal implementation**

```python
# app/api/routes.py
@router.get("/task/{task_id}")
async def get_task(task_id: str):
    task = task_service.get_task(task_id)
    return {"task_id": task.task_id, "status": task.status}


@router.get("/plan/{session_id}/history")
async def get_plan_history(session_id: str, limit: int = 5):
    history = state_service.get_plan_history(session_id, limit)
    return {"session_id": session_id, "history": history}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_task_api.py tests/test_session_plan_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api app/services tests/test_task_api.py tests/test_session_plan_api.py
git commit -m "feat: add task query and plan history endpoints"
```

### Task 5: 恢复策略与全链路回归

**Files:**
- Modify: `app/workers/task_worker.py`
- Modify: `app/services/task_service.py`
- Modify: `app/config/settings.py`
- Modify: `tests/test_worker_recovery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worker_recovery.py
def test_worker_can_resume_running_task(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    repository.seed_running_task(task_id="t-resume", session_id="s-1")

    worker = TaskWorker(**fake_worker_deps)
    recovered = worker.resume_incomplete_tasks()

    assert "t-resume" in recovered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker_recovery.py::test_worker_can_resume_running_task -v`
Expected: FAIL missing method

- [ ] **Step 3: Write minimal implementation**

```python
# app/workers/task_worker.py
def resume_incomplete_tasks(self) -> list[str]:
    recovered: list[str] = []
    for task in self.repository.list_recoverable_tasks():
        self.process_one({"task_id": task.task_id, "session_id": task.session_id, "message": ""})
        recovered.append(task.task_id)
    return recovered
```

- [ ] **Step 4: Run full test suite and verify**

Run: `pytest -v -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/workers app/services app/config tests/test_worker_recovery.py
git commit -m "feat: add task recovery flow and end-to-end regression"
```

## 自检结果

1. Spec coverage:
- 覆盖了异步任务创建、队列消费、执行回填、状态恢复、结果查询。
- 覆盖了 Redis 运行层与 MySQL 权威层协作路径。
- 覆盖了并发闭环的关键接口：`/chat`、`/task/{id}`、`/plan/{id}/history`。

2. Placeholder scan:
- 未使用 TBD/TODO 等占位语句。
- 每个任务都给出明确文件、测试与命令。

3. Type consistency:
- `task_id`、`session_id` 在 API、Service、Repository、Worker 之间保持一致。
- 任务状态值统一使用字符串枚举（PENDING/RUNNING/SUCCEEDED/FAILED/CANCELED）。
