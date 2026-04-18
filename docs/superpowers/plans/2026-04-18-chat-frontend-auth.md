# Chat Frontend Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a consumer-style chat frontend and basic account system for the multi-agent travel planner.

**Architecture:** The backend adds first-party username/email authentication, signed bearer tokens, and user ownership checks around sessions, tasks, and plans. The frontend lives in `frontend/` as a Vite React TypeScript app that talks to the FastAPI API, keeps auth state in local storage, and presents a full-screen chat experience with history and plan drawers.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React, Vite, TypeScript, Vitest, Testing Library.

---

## File Structure

- `app/db/models.py`: add `User` model and owner columns for task/session/plan rows.
- `app/db/repository.py`: create users, look up users, store ownership, and filter reads by user.
- `app/services/security.py`: password hashing and token signing/verification helpers.
- `app/services/auth_service.py`: registration, login, current-user lookup.
- `app/api/auth.py`: `/auth/register`, `/auth/login`, `/auth/me`.
- `app/api/routes.py`: include auth dependency on user-owned travel endpoints while preserving anonymous compatibility for existing tests where needed.
- `app/api/schemas.py`: auth request/response models.
- `tests/test_auth_api.py`: backend auth API tests.
- `tests/test_user_isolation.py`: ownership and cross-user access tests.
- `frontend/`: Vite React TypeScript app.
- `frontend/src/api/client.ts`: typed API client and bearer token handling.
- `frontend/src/auth/AuthContext.tsx`: auth state, login, register, logout, route guard helpers.
- `frontend/src/pages/LoginPage.tsx`: login page.
- `frontend/src/pages/RegisterPage.tsx`: registration page.
- `frontend/src/pages/ChatPage.tsx`: main chat page.
- `frontend/src/components/HistoryDrawer.tsx`: history drawer.
- `frontend/src/components/PlanDrawer.tsx`: plan details drawer.
- `frontend/src/components/ChatComposer.tsx`: fixed message input.
- `frontend/src/components/MessageList.tsx`: chat messages and task progress.
- `frontend/src/styles.css`: responsive consumer chat styling.
- `frontend/src/__tests__/auth-flow.test.tsx`: auth flow tests.
- `frontend/src/__tests__/chat-flow.test.tsx`: chat and plan drawer tests.

## Task 1: Backend User Model And Auth Service

**Files:**
- Modify: `app/db/models.py`
- Modify: `app/db/repository.py`
- Create: `app/services/security.py`
- Create: `app/services/auth_service.py`
- Modify: `app/services/__init__.py`
- Test: `tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_register_login_and_me_flow():
    client = TestClient(app)

    register = client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "pass12345"},
    )

    assert register.status_code == 201
    assert register.json()["user"]["username"] == "alice"
    assert "access_token" in register.json()
    assert "password" not in register.text

    login = client.post(
        "/auth/login",
        json={"identifier": "alice@example.com", "password": "pass12345"},
    )

    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_register_rejects_duplicate_email():
    client = TestClient(app)
    payload = {"username": "bob", "email": "bob@example.com", "password": "pass12345"}

    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json={**payload, "username": "bobby"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "USER_ALREADY_EXISTS"


def test_login_rejects_wrong_password():
    client = TestClient(app)
    client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "pass12345"},
    )

    response = client.post(
        "/auth/login",
        json={"identifier": "carol@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
conda run -n leetcode pytest tests/test_auth_api.py -q -p no:cacheprovider
```

Expected: the tests fail because `/auth/register`, `/auth/login`, and `/auth/me` do not exist yet.

- [ ] **Step 3: Add the database model and repository methods**

In `app/db/models.py`, add:

```python
class User(Base):
    __tablename__ = "users"

    user_id = Column(String(32), primary_key=True, default=lambda: f"u-{uuid4().hex[:12]}")
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

In `app/db/repository.py`, import `User` and add:

```python
    def create_user(self, username: str, email: str, password_hash: str) -> User:
        with self._session_factory() as db:
            user = User(username=username, email=email, password_hash=password_hash)
            db.add(user)
            db.commit()
            return user

    def get_user_by_identifier(self, identifier: str) -> User | None:
        with self._session_factory() as db:
            stmt = select(User).where((User.email == identifier) | (User.username == identifier))
            return db.scalar(stmt)

    def get_user(self, user_id: str) -> User | None:
        with self._session_factory() as db:
            return db.get(User, user_id)
```

- [ ] **Step 4: Add security and auth services**

Create `app/services/security.py`:

```python
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from secrets import compare_digest


TOKEN_SECRET = os.environ.get("AUTH_TOKEN_SECRET", "dev-only-token-secret")
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt = salt or base64.urlsafe_b64encode(os.urandom(16)).decode("ascii")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${salt}${encoded_digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, salt=salt).split("$", 2)[2]
    return compare_digest(candidate, expected)


def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_part = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    signature_part = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload_part}.{signature_part}"


def verify_access_token(token: str) -> str | None:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError:
        return None
    expected_signature = hmac.new(
        TOKEN_SECRET.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256
    ).digest()
    expected_part = base64.urlsafe_b64encode(expected_signature).decode("ascii").rstrip("=")
    if not hmac.compare_digest(signature_part, expected_part):
        return None
    padded_payload = payload_part + "=" * (-len(payload_part) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded_payload.encode("ascii")))
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return str(payload.get("sub") or "")
```

Create `app/services/auth_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.db.repository import TaskRepository
from app.services.security import create_access_token, hash_password, verify_access_token, verify_password


@dataclass
class AuthResult:
    user: dict
    access_token: str


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class AuthService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def register(self, username: str, email: str, password: str) -> AuthResult:
        try:
            user = self.repository.create_user(username, email, hash_password(password))
        except IntegrityError as exc:
            raise AuthError("USER_ALREADY_EXISTS", "user already exists", 409) from exc
        return AuthResult(user=self._public_user(user), access_token=create_access_token(user.user_id))

    def login(self, identifier: str, password: str) -> AuthResult:
        user = self.repository.get_user_by_identifier(identifier)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("INVALID_CREDENTIALS", "invalid credentials", 401)
        return AuthResult(user=self._public_user(user), access_token=create_access_token(user.user_id))

    def get_current_user(self, token: str) -> dict:
        user_id = verify_access_token(token)
        if not user_id:
            raise AuthError("UNAUTHENTICATED", "authentication required", 401)
        user = self.repository.get_user(user_id)
        if user is None:
            raise AuthError("UNAUTHENTICATED", "authentication required", 401)
        return self._public_user(user)

    def _public_user(self, user) -> dict:
        return {"user_id": user.user_id, "username": user.username, "email": user.email}
```

- [ ] **Step 5: Export the service**

In `app/services/__init__.py`, add:

```python
from app.services.auth_service import AuthError, AuthResult, AuthService
```

- [ ] **Step 6: Run focused tests and verify they still fail at the route layer**

Run:

```powershell
conda run -n leetcode pytest tests/test_auth_api.py -q -p no:cacheprovider
```

Expected: tests still fail because auth routes are not included yet, while import errors are gone.

- [ ] **Step 7: Commit**

Run:

```powershell
git add app/db/models.py app/db/repository.py app/services/security.py app/services/auth_service.py app/services/__init__.py tests/test_auth_api.py
git commit -m "feat: add user auth service"
```

## Task 2: Backend Auth Routes

**Files:**
- Modify: `app/api/schemas.py`
- Create: `app/api/auth.py`
- Modify: `app/main.py`
- Test: `tests/test_auth_api.py`

- [ ] **Step 1: Add auth schemas**

In `app/api/schemas.py`, add:

```python
class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 2: Create auth routes**

Create `app/api/auth.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.api.routes import task_repository
from app.services.auth_service import AuthError, AuthService
from app.utils.error_codes import build_error

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService(task_repository)


def _token_from_header(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AuthError("UNAUTHENTICATED", "authentication required", 401)
    return header.removeprefix("Bearer ").strip()


def _auth_error(exc: AuthError, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error(exc.code, str(exc), request_id=getattr(request.state, "request_id", None)),
    )


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(payload: RegisterRequest, request: Request):
    try:
        result = auth_service.register(payload.username, payload.email, payload.password)
        return {"user": result.user, "access_token": result.access_token, "token_type": "bearer"}
    except AuthError as exc:
        return _auth_error(exc, request)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request):
    try:
        result = auth_service.login(payload.identifier, payload.password)
        return {"user": result.user, "access_token": result.access_token, "token_type": "bearer"}
    except AuthError as exc:
        return _auth_error(exc, request)


@router.get("/me", response_model=UserResponse)
async def me(request: Request):
    try:
        return auth_service.get_current_user(_token_from_header(request))
    except AuthError as exc:
        return _auth_error(exc, request)
```

- [ ] **Step 3: Include the auth router**

In `app/main.py`, import and include:

```python
from app.api.auth import router as auth_router
```

Then after `app.include_router(router)` add:

```python
app.include_router(auth_router)
```

- [ ] **Step 4: Run auth tests and verify they pass**

Run:

```powershell
conda run -n leetcode pytest tests/test_auth_api.py -q -p no:cacheprovider
```

Expected: `3 passed`.

- [ ] **Step 5: Run existing API tests**

Run:

```powershell
conda run -n leetcode pytest tests/test_task_api.py tests/test_session_plan_api.py -q -p no:cacheprovider
```

Expected: existing tests pass with no auth regression.

- [ ] **Step 6: Commit**

Run:

```powershell
git add app/api/schemas.py app/api/auth.py app/main.py tests/test_auth_api.py
git commit -m "feat: add auth api routes"
```

## Task 3: User Ownership For Tasks, Sessions, And Plans

**Files:**
- Modify: `app/db/models.py`
- Modify: `app/db/repository.py`
- Modify: `app/services/task_service.py`
- Modify: `app/api/routes.py`
- Test: `tests/test_user_isolation.py`

- [ ] **Step 1: Write failing isolation tests**

Create `tests/test_user_isolation.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, username: str, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": "pass12345"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_user_cannot_read_another_users_task():
    client = TestClient(app)
    alice = _register(client, "isoalice", "isoalice@example.com")
    bob = _register(client, "isobob", "isobob@example.com")

    create = client.post(
        "/chat/async",
        json={"message": "帮我规划杭州两日游"},
        headers={"Authorization": f"Bearer {alice}"},
    )
    assert create.status_code == 202
    task_id = create.json()["task_id"]

    blocked = client.get(f"/task/{task_id}", headers={"Authorization": f"Bearer {bob}"})

    assert blocked.status_code == 404
    assert blocked.json()["code"] == "TASK_NOT_FOUND"


def test_user_cannot_read_another_users_plan_history():
    client = TestClient(app)
    alice = _register(client, "planalice", "planalice@example.com")
    bob = _register(client, "planbob", "planbob@example.com")

    chat = client.post(
        "/chat",
        json={"message": "帮我规划杭州两日游"},
        headers={"Authorization": f"Bearer {alice}"},
    )
    assert chat.status_code == 200
    session_id = chat.json()["session_id"]

    blocked = client.get(f"/plan/{session_id}/history", headers={"Authorization": f"Bearer {bob}"})

    assert blocked.status_code == 404
    assert blocked.json()["code"] == "PLAN_NOT_FOUND"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
conda run -n leetcode pytest tests/test_user_isolation.py -q -p no:cacheprovider
```

Expected: tests fail because task and plan reads are not filtered by user.

- [ ] **Step 3: Add ownership columns**

In `app/db/models.py`, add nullable `user_id` columns so legacy anonymous tests keep working:

```python
user_id = Column(String(32), ForeignKey("users.user_id"), index=True, nullable=True)
```

Add it to `Task`, `PlanSnapshot`, and `SessionState`.

In `TaskRepository.__init__`, add a helper call after `_ensure_task_payload_column()`:

```python
self._ensure_owner_columns()
```

Add this method:

```python
    def _ensure_owner_columns(self) -> None:
        inspector = inspect(self.engine)
        for table_name in ["tasks", "plan_snapshots", "session_states"]:
            if not inspector.has_table(table_name):
                continue
            column_names = {column["name"] for column in inspector.get_columns(table_name)}
            if "user_id" not in column_names:
                with self.engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN user_id VARCHAR(32)"))
```

- [ ] **Step 4: Add repository ownership methods**

In `app/db/repository.py`, update signatures:

```python
    def create_task(
        self,
        session_id: str,
        task_type: str,
        payload_json: dict | None = None,
        user_id: str | None = None,
    ) -> str:
```

Set `user_id=user_id` on `Task`.

Update `save_plan_snapshot` and `upsert_session_state` signatures to accept `user_id: str | None = None`, then set `user_id` in inserted values.

Add owned reads:

```python
    def get_task_for_user(self, task_id: str, user_id: str | None) -> Task:
        task = self.get_task(task_id)
        if user_id is not None and task.user_id not in {None, user_id}:
            raise KeyError(f"Task not found: {task_id}")
        return task

    def get_plan_history_for_user(self, session_id: str, limit: int, user_id: str | None) -> list[PlanSnapshot]:
        with self._session_factory() as db:
            stmt = select(PlanSnapshot).where(PlanSnapshot.session_id == session_id)
            if user_id is not None:
                stmt = stmt.where(PlanSnapshot.user_id == user_id)
            stmt = stmt.order_by(desc(PlanSnapshot.version)).limit(max(limit, 0))
            rows = list(db.scalars(stmt))
            rows.reverse()
            return rows
```

- [ ] **Step 5: Pass user ID through task creation**

In `app/services/task_service.py`, update `create_chat_task` to accept `user_id: str | None = None`, pass it to `repository.create_task`, and add it to payload:

```python
payload = {"task_id": task_id, "session_id": session_id, "message": message}
if request_id is not None:
    payload["request_id"] = request_id
if user_id is not None:
    payload["user_id"] = user_id
```

- [ ] **Step 6: Add optional user extraction to routes**

In `app/api/routes.py`, import auth helpers and add:

```python
from app.api.auth import auth_service


def _optional_user_id(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        return auth_service.get_current_user(header.removeprefix("Bearer ").strip())["user_id"]
    except Exception:
        return None
```

Use `_optional_user_id(http_request)` in `/chat/async` when calling `create_chat_task`.

Use `task_service.get_task_for_user(task_id, _optional_user_id(request))` in task read/cancel/steps handlers. If the optional user ID is present and ownership does not match, return the existing `TASK_NOT_FOUND` 404.

Use `task_repository.get_plan_history_for_user(session_id, limit, _optional_user_id(request))` in `/plan/{session_id}/history`.

- [ ] **Step 7: Run isolation tests and verify they pass**

Run:

```powershell
conda run -n leetcode pytest tests/test_user_isolation.py -q -p no:cacheprovider
```

Expected: `2 passed`.

- [ ] **Step 8: Run backend regression tests**

Run:

```powershell
conda run -n leetcode pytest tests/test_auth_api.py tests/test_task_api.py tests/test_session_plan_api.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit**

Run:

```powershell
git add app/db/models.py app/db/repository.py app/services/task_service.py app/api/routes.py tests/test_user_isolation.py
git commit -m "feat: enforce user-owned travel resources"
```

## Task 4: Frontend Project Skeleton And Auth Flow

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/RegisterPage.tsx`
- Create: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/auth-flow.test.tsx`

- [ ] **Step 1: Create frontend package files**

Create `frontend/package.json`:

```json
{
  "name": "travel-planner-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "test": "vitest run --environment jsdom"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "typescript": "^5.8.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.6.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "jsdom": "^26.0.0",
    "vitest": "^3.0.0"
  }
}
```

Create `frontend/index.html`:

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

- [ ] **Step 2: Write failing auth UI test**

Create `frontend/src/__tests__/auth-flow.test.tsx`:

```tsx
import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "../App";

describe("auth flow", () => {
  it("logs in and shows the chat page", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/auth/login")) {
        return new Response(JSON.stringify({
          access_token: "token-1",
          token_type: "bearer",
          user: { user_id: "u-1", username: "alice", email: "alice@example.com" }
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("{}", { status: 404 });
    }));

    render(<App />);

    await userEvent.type(screen.getByLabelText("账号"), "alice@example.com");
    await userEvent.type(screen.getByLabelText("密码"), "pass12345");
    await userEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(screen.getByText("今天想去哪里？")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Run the frontend test and verify it fails**

Run:

```powershell
cd frontend
npm install
npm test -- auth-flow.test.tsx
```

Expected: test fails because `src/App.tsx` does not exist.

- [ ] **Step 4: Add API client and auth context**

Create `frontend/src/api/client.ts`:

```ts
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type AuthUser = { user_id: string; username: string; email: string };
export type AuthResponse = { user: AuthUser; access_token: string; token_type: string };

export async function apiFetch<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || data.code || "请求失败");
  }
  return data as T;
}
```

Create `frontend/src/auth/AuthContext.tsx`:

```tsx
import { createContext, useContext, useMemo, useState } from "react";
import { apiFetch, type AuthResponse, type AuthUser } from "../api/client";

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  login(identifier: string, password: string): Promise<void>;
  register(username: string, email: string, password: string): Promise<void>;
  logout(): void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem("travel_token"));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem("travel_user");
    return raw ? JSON.parse(raw) : null;
  });

  async function persist(result: AuthResponse) {
    localStorage.setItem("travel_token", result.access_token);
    localStorage.setItem("travel_user", JSON.stringify(result.user));
    setToken(result.access_token);
    setUser(result.user);
  }

  const value = useMemo<AuthContextValue>(() => ({
    user,
    token,
    async login(identifier: string, password: string) {
      const result = await apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });
      await persist(result);
    },
    async register(username: string, email: string, password: string) {
      const result = await apiFetch<AuthResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      });
      await persist(result);
    },
    logout() {
      localStorage.removeItem("travel_token");
      localStorage.removeItem("travel_user");
      setToken(null);
      setUser(null);
    },
  }), [token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
```

- [ ] **Step 5: Add login/register pages and app shell**

Create `frontend/src/pages/LoginPage.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";

export function LoginPage({ onShowRegister }: { onShowRegister(): void }) {
  const auth = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await auth.login(identifier, password);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "登录失败");
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-panel" onSubmit={submit}>
        <h1>旅行规划助手</h1>
        <p>登录后继续你的旅行计划。</p>
        <label>账号<input value={identifier} onChange={(e) => setIdentifier(e.target.value)} /></label>
        <label>密码<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p role="alert" className="error-text">{error}</p>}
        <button type="submit">登录</button>
        <button type="button" className="link-button" onClick={onShowRegister}>创建账号</button>
      </form>
    </main>
  );
}
```

Create `frontend/src/pages/RegisterPage.tsx` with the same structure and fields `username`、`email`、`password`、`confirmPassword`; call `auth.register`.

Create `frontend/src/App.tsx`:

```tsx
import { useState } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ChatPage } from "./pages/ChatPage";
import "./styles.css";

function AppContent() {
  const auth = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  if (!auth.user) {
    return mode === "login"
      ? <LoginPage onShowRegister={() => setMode("register")} />
      : <RegisterPage onShowLogin={() => setMode("login")} />;
  }
  return <ChatPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
```

Create `frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 6: Add temporary ChatPage and styles**

Create `frontend/src/pages/ChatPage.tsx`:

```tsx
import { useAuth } from "../auth/AuthContext";

export function ChatPage() {
  const auth = useAuth();
  return (
    <main className="chat-shell">
      <header className="topbar">
        <strong>旅行规划助手</strong>
        <button onClick={auth.logout}>退出</button>
      </header>
      <section className="empty-chat">
        <h1>今天想去哪里？</h1>
        <p>告诉我出发地、目的地、时间、预算和偏好。</p>
      </section>
    </main>
  );
}
```

Create `frontend/src/styles.css` with accessible base styles:

```css
:root {
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #172026;
  background: #f7f9fb;
}

* { box-sizing: border-box; }
body { margin: 0; min-width: 320px; }
button, input, textarea { font: inherit; }
button { min-height: 44px; border-radius: 8px; border: 1px solid #1f6f68; background: #1f6f68; color: #fff; padding: 0 16px; cursor: pointer; }
button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 3px solid #4fb7ad; outline-offset: 2px; }
.link-button { background: transparent; color: #1f6f68; }
.auth-page { min-height: 100dvh; display: grid; place-items: center; padding: 24px; }
.auth-panel { width: min(420px, 100%); display: grid; gap: 16px; background: #fff; padding: 24px; border: 1px solid #d8e1e8; border-radius: 8px; }
.auth-panel label { display: grid; gap: 6px; font-weight: 600; }
.auth-panel input { min-height: 44px; border: 1px solid #a7b5bf; border-radius: 8px; padding: 0 12px; }
.error-text { color: #b42318; margin: 0; }
.chat-shell { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr; }
.topbar { min-height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; border-bottom: 1px solid #d8e1e8; background: #fff; }
.empty-chat { display: grid; place-content: center; text-align: center; padding: 24px; }
```

- [ ] **Step 7: Run frontend auth tests and verify they pass**

Run:

```powershell
cd frontend
npm test -- auth-flow.test.tsx
```

Expected: the auth flow test passes.

- [ ] **Step 8: Commit**

Run:

```powershell
git add frontend
git commit -m "feat: add chat frontend auth shell"
```

## Task 5: Frontend Chat Flow, Task Progress, And Plan Drawer

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/components/ChatComposer.tsx`
- Create: `frontend/src/components/MessageList.tsx`
- Create: `frontend/src/components/HistoryDrawer.tsx`
- Create: `frontend/src/components/PlanDrawer.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/chat-flow.test.tsx`

- [ ] **Step 1: Write failing chat flow test**

Create `frontend/src/__tests__/chat-flow.test.tsx`:

```tsx
import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "../App";

describe("chat flow", () => {
  it("submits a travel request and opens plan drawer", async () => {
    localStorage.setItem("travel_token", "token-1");
    localStorage.setItem("travel_user", JSON.stringify({ user_id: "u-1", username: "alice", email: "alice@example.com" }));
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/chat/async")) {
        return new Response(JSON.stringify({ task_id: "t-1", session_id: "s-1", status: "PENDING" }), { status: 202, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/task/t-1")) {
        return new Response(JSON.stringify({ task_id: "t-1", session_id: "s-1", status: "SUCCEEDED" }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/plan/s-1")) {
        return new Response(JSON.stringify({
          overview: "杭州两日游",
          transport: [{ name: "高铁", price: 180 }],
          hotels: [{ name: "西湖附近酒店", price: 520 }],
          itinerary: [{ day: 1, title: "西湖与湖滨" }],
          budget: { total: 2200 },
          notes: ["提前预约热门景点"]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("{}", { status: 404 });
    }));

    render(<App />);

    await userEvent.type(screen.getByLabelText("旅行需求"), "帮我规划杭州两日游");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(screen.getByText("杭州两日游")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "查看完整方案" }));

    expect(screen.getByText("交通推荐")).toBeInTheDocument();
    expect(screen.getByText("西湖附近酒店")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run chat flow test and verify it fails**

Run:

```powershell
cd frontend
npm test -- chat-flow.test.tsx
```

Expected: test fails because composer, polling, and plan drawer are not implemented.

- [ ] **Step 3: Extend API client**

Add to `frontend/src/api/client.ts`:

```ts
export type ChatTask = { task_id: string; session_id: string; status: string };
export type TravelPlan = {
  overview?: string;
  transport?: Array<Record<string, unknown>>;
  hotels?: Array<Record<string, unknown>>;
  itinerary?: Array<Record<string, unknown>>;
  budget?: Record<string, unknown>;
  notes?: string[];
};

export function createChatTask(message: string, token: string) {
  return apiFetch<ChatTask>("/chat/async", {
    method: "POST",
    body: JSON.stringify({ message }),
  }, token);
}

export function getTask(taskId: string, token: string) {
  return apiFetch<ChatTask>(`/task/${taskId}`, {}, token);
}

export function getPlan(sessionId: string, token: string) {
  return apiFetch<TravelPlan>(`/plan/${sessionId}`, {}, token);
}
```

- [ ] **Step 4: Add chat components**

Create `frontend/src/components/ChatComposer.tsx`:

```tsx
import { FormEvent, useState } from "react";

export function ChatComposer({ disabled, onSubmit }: { disabled: boolean; onSubmit(message: string): void }) {
  const [message, setMessage] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setMessage("");
  }
  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="travel-message">旅行需求</label>
      <textarea id="travel-message" value={message} onChange={(e) => setMessage(e.target.value)} rows={2} />
      <button type="submit" disabled={disabled}>{disabled ? "生成中" : "发送"}</button>
    </form>
  );
}
```

Create `frontend/src/components/MessageList.tsx`:

```tsx
export type ChatMessage = { role: "user" | "assistant" | "status"; content: string };

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <section className="messages" aria-live="polite">
      {messages.map((message, index) => (
        <article key={index} className={`message ${message.role}`}>
          {message.content}
        </article>
      ))}
    </section>
  );
}
```

Create `frontend/src/components/PlanDrawer.tsx`:

```tsx
import type { TravelPlan } from "../api/client";

export function PlanDrawer({ open, plan, onClose }: { open: boolean; plan: TravelPlan | null; onClose(): void }) {
  if (!open || !plan) return null;
  return (
    <aside className="plan-drawer" aria-label="完整旅行方案">
      <button className="drawer-close" onClick={onClose}>关闭</button>
      <h2>{plan.overview || "旅行方案"}</h2>
      <section><h3>交通推荐</h3>{plan.transport?.map((item, i) => <p key={i}>{String(item.name || "交通方案")}</p>)}</section>
      <section><h3>酒店推荐</h3>{plan.hotels?.map((item, i) => <p key={i}>{String(item.name || "酒店方案")}</p>)}</section>
      <section><h3>每日行程</h3>{plan.itinerary?.map((item, i) => <p key={i}>{String(item.title || `Day ${item.day || i + 1}`)}</p>)}</section>
      <section><h3>预算估算</h3><p>{String(plan.budget?.total || "待估算")}</p></section>
      <section><h3>注意事项</h3>{plan.notes?.map((note, i) => <p key={i}>{note}</p>)}</section>
    </aside>
  );
}
```

Create `frontend/src/components/HistoryDrawer.tsx`:

```tsx
export function HistoryDrawer({ open, onClose }: { open: boolean; onClose(): void }) {
  if (!open) return null;
  return (
    <aside className="history-drawer" aria-label="历史会话">
      <button onClick={onClose}>关闭历史</button>
      <p>还没有历史会话，开始第一次旅行规划吧。</p>
    </aside>
  );
}
```

- [ ] **Step 5: Implement ChatPage behavior**

Replace `frontend/src/pages/ChatPage.tsx` with:

```tsx
import { useState } from "react";
import { createChatTask, getPlan, getTask, type TravelPlan } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ChatComposer } from "../components/ChatComposer";
import { HistoryDrawer } from "../components/HistoryDrawer";
import { MessageList, type ChatMessage } from "../components/MessageList";
import { PlanDrawer } from "../components/PlanDrawer";

export function ChatPage() {
  const auth = useAuth();
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [plan, setPlan] = useState<TravelPlan | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  async function submit(message: string) {
    if (!auth.token) return;
    setBusy(true);
    setMessages((items) => [...items, { role: "user", content: message }, { role: "status", content: "正在生成旅行方案" }]);
    try {
      const task = await createChatTask(message, auth.token);
      const latest = await getTask(task.task_id, auth.token);
      if (latest.status === "SUCCEEDED" || latest.status === "WAITING_INPUT") {
        const nextPlan = await getPlan(task.session_id, auth.token);
        setPlan(nextPlan);
        setMessages((items) => [
          ...items.filter((item) => item.role !== "status"),
          { role: "assistant", content: nextPlan.overview || "旅行方案已生成" },
        ]);
      }
    } catch (exc) {
      setMessages((items) => [...items.filter((item) => item.role !== "status"), { role: "assistant", content: exc instanceof Error ? exc.message : "生成失败，请重试" }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="chat-shell">
      <header className="topbar">
        <button className="link-button" onClick={() => setHistoryOpen(true)}>历史</button>
        <strong>旅行规划助手</strong>
        <button className="link-button" onClick={auth.logout}>退出</button>
      </header>
      {messages.length === 0 ? (
        <section className="empty-chat">
          <h1>今天想去哪里？</h1>
          <p>告诉我出发地、目的地、时间、预算和偏好。</p>
        </section>
      ) : (
        <MessageList messages={messages} />
      )}
      {plan && <button className="plan-button" onClick={() => setPlanOpen(true)}>查看完整方案</button>}
      <ChatComposer disabled={busy} onSubmit={submit} />
      <HistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} />
      <PlanDrawer open={planOpen} plan={plan} onClose={() => setPlanOpen(false)} />
    </main>
  );
}
```

- [ ] **Step 6: Add responsive drawer styles**

Append to `frontend/src/styles.css`:

```css
.messages { padding: 24px; display: grid; align-content: start; gap: 12px; overflow: auto; }
.message { max-width: min(720px, 90%); padding: 12px 14px; border-radius: 8px; line-height: 1.5; }
.message.user { justify-self: end; background: #1f6f68; color: #fff; }
.message.assistant, .message.status { justify-self: start; background: #fff; border: 1px solid #d8e1e8; }
.composer { position: sticky; bottom: 0; display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 16px; background: #fff; border-top: 1px solid #d8e1e8; }
.composer label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.composer textarea { min-height: 52px; resize: vertical; border: 1px solid #a7b5bf; border-radius: 8px; padding: 12px; }
.plan-button { position: fixed; right: 16px; bottom: 96px; }
.plan-drawer, .history-drawer { position: fixed; inset: 0 0 0 auto; width: min(420px, 100%); overflow: auto; background: #fff; border-left: 1px solid #d8e1e8; padding: 20px; box-shadow: 0 20px 60px rgb(23 32 38 / 18%); }
.history-drawer { inset: 0 auto 0 0; border-left: 0; border-right: 1px solid #d8e1e8; }
.drawer-close { margin-bottom: 16px; }
@media (max-width: 720px) {
  .composer { grid-template-columns: 1fr; }
  .plan-button { left: 16px; right: 16px; bottom: 124px; }
}
```

- [ ] **Step 7: Run frontend tests and build**

Run:

```powershell
cd frontend
npm test
npm run build
```

Expected: all frontend tests pass and Vite build completes.

- [ ] **Step 8: Commit**

Run:

```powershell
git add frontend
git commit -m "feat: add chat frontend plan flow"
```

## Task 6: Documentation And Full Verification

**Files:**
- Modify: `README.md` if present, otherwise create: `README.md`
- Modify: `多智能体旅行规划助手_需求开发总结.md`
- Test: backend and frontend verification commands

- [ ] **Step 1: Update README**

Add these sections:

```markdown
## Frontend

The consumer chat frontend lives in `frontend/`.

```powershell
cd frontend
npm install
npm run dev
```

The frontend reads `VITE_API_BASE_URL`; when it is not set, it calls `http://127.0.0.1:8000`.

## Auth

The backend exposes:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Authenticated frontend requests use `Authorization: Bearer <token>`.
```

- [ ] **Step 2: Update project summary**

In `多智能体旅行规划助手_需求开发总结.md`, add a short progress note under the frontend/account section:

```markdown
### 前端与账号体系实施进展

- 已规划普通用户聊天应用风格 Web 前端。
- 第一版包含登录、注册、聊天首页、历史侧栏、方案详情抽屉。
- 后端账号体系包含用户注册、登录、当前用户和用户级资源隔离。
```

- [ ] **Step 3: Run backend full test suite**

Run:

```powershell
conda run -n leetcode pytest -q -p no:cacheprovider
```

Expected: all backend tests pass.

- [ ] **Step 4: Run frontend full test and build**

Run:

```powershell
cd frontend
npm test
npm run build
```

Expected: frontend tests pass and production build completes.

- [ ] **Step 5: Commit**

Run:

```powershell
git add README.md 多智能体旅行规划助手_需求开发总结.md
git commit -m "docs: document frontend auth workflow"
```

## Self-Review

Spec coverage:

- Auth pages and API are covered by Tasks 1, 2, and 4.
- User-level resource isolation is covered by Task 3.
- Consumer chat homepage, history drawer, plan drawer, task progress, and responsive styling are covered by Tasks 4 and 5.
- Documentation and verification are covered by Task 6.

Scope decisions:

- Third-party login, password reset, admin pages, payment, native mobile apps, and complex dashboards remain outside this first implementation.
- Existing anonymous backend tests are kept compatible by using nullable ownership columns and optional auth extraction.

Type consistency:

- Auth API uses `user_id`, `username`, `email`, `access_token`, and `token_type` consistently across backend and frontend.
- Frontend `TravelPlan` intentionally accepts flexible record values because current backend plan payloads are mock-oriented and not fully typed.
