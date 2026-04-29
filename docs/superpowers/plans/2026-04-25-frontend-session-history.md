# Frontend Session History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mocked frontend history with real saved chat session entries and plan restoration.

**Architecture:** The frontend stores a lightweight per-user session index in localStorage after successful chat generation. HistoryDrawer reads that index, fetches each session's latest plan history through existing backend APIs, and lets ChatPage restore the selected plan.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing FastAPI endpoints.

---

### Task 1: Add Session History API Helpers

**Files:**
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/src/__tests__/chat-flow.test.tsx`

- [ ] Write failing tests proving history uses real API data and does not render mock sessions.
- [ ] Add typed `PlanHistoryResponse`, `SessionHistoryEntry`, `readSessionHistory`, `rememberSession`, and `forgetSessionHistory`.
- [ ] Run frontend tests.

### Task 2: Wire ChatPage Session State

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`
- Test: `frontend/src/__tests__/chat-flow.test.tsx`

- [ ] Store the current `session_id` after task creation succeeds.
- [ ] Remember session preview after plan generation.
- [ ] Make new conversation reset messages, plan, current session, and composer.
- [ ] Gate history and my plans behind login.

### Task 3: Replace Mock HistoryDrawer

**Files:**
- Modify: `frontend/src/components/HistoryDrawer.tsx`
- Test: `frontend/src/__tests__/chat-flow.test.tsx`

- [ ] Load stored sessions when opened.
- [ ] Fetch plan history for each stored session.
- [ ] Render real titles/previews/dates.
- [ ] On click, pass selected `session_id` and latest plan back to ChatPage.

### Verification

- [ ] `npm test -- --run`
- [ ] `npm run build`
