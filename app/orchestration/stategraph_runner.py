from __future__ import annotations

import copy
import inspect
from collections.abc import Callable
from typing import Any


EmitStep = Callable[[str, dict, dict], Any]


class StateGraphRunner:
    """StateGraph execution entrypoint with node-level checkpoint recovery."""

    NODE_ORDER = ("ingest", "planner", "finalize")

    def __init__(self, chat_service) -> None:
        self.chat_service = chat_service

    @classmethod
    def _normalize_checkpoint(cls, checkpoint: dict | None) -> dict:
        normalized = dict(checkpoint or {}) if isinstance(checkpoint, dict) else {}
        raw_completed = normalized.get("completed_nodes", [])
        completed_nodes: list[str] = []
        if isinstance(raw_completed, list):
            for node in raw_completed:
                if node in cls.NODE_ORDER and node not in completed_nodes:
                    completed_nodes.append(node)

        raw_outputs = normalized.get("node_outputs", {})
        normalized["completed_nodes"] = completed_nodes
        normalized["node_outputs"] = dict(raw_outputs) if isinstance(raw_outputs, dict) else {}
        normalized.setdefault("version", 1)
        return normalized

    @staticmethod
    def _checkpoint_snapshot(checkpoint: dict) -> dict:
        return copy.deepcopy(checkpoint)

    @staticmethod
    def _node_completed(checkpoint: dict, node: str) -> bool:
        return node in checkpoint["completed_nodes"] and node in checkpoint["node_outputs"]

    async def _emit(
        self,
        emit_step: EmitStep | None,
        node: str,
        output: dict,
        checkpoint: dict,
    ) -> None:
        if emit_step is None:
            return
        maybe_awaitable = emit_step(
            node,
            copy.deepcopy(output),
            self._checkpoint_snapshot(checkpoint),
        )
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    async def _complete_node(
        self,
        checkpoint: dict,
        node: str,
        output: dict,
        emit_step: EmitStep | None,
    ) -> dict:
        checkpoint["node_outputs"][node] = copy.deepcopy(output)
        if node not in checkpoint["completed_nodes"]:
            checkpoint["completed_nodes"].append(node)
        await self._emit(emit_step, node, output, checkpoint)
        return output

    async def _run_ingest(
        self,
        session_id: str,
        message: str,
        checkpoint: dict,
        emit_step: EmitStep | None,
    ) -> dict:
        if self._node_completed(checkpoint, "ingest"):
            return checkpoint["node_outputs"]["ingest"]
        return await self._complete_node(
            checkpoint,
            "ingest",
            {"session_id": session_id, "message": message},
            emit_step,
        )

    async def _run_planner(
        self,
        ingest_output: dict,
        checkpoint: dict,
        emit_step: EmitStep | None,
    ) -> dict:
        if self._node_completed(checkpoint, "planner"):
            return checkpoint["node_outputs"]["planner"]

        from app.api.schemas import ChatRequest

        response = await self.chat_service.process_message(
            ChatRequest(
                message=str(ingest_output.get("message", "")),
                session_id=str(ingest_output["session_id"]),
            )
        )
        output = {
            "session_id": response.session_id,
            "response": response.response,
            "updated_plan": response.updated_plan,
            "pending_questions": response.pending_questions,
            "needs_user_input": bool(response.pending_questions),
        }
        return await self._complete_node(checkpoint, "planner", output, emit_step)

    async def _run_finalize(
        self,
        planner_output: dict,
        checkpoint: dict,
        emit_step: EmitStep | None,
    ) -> dict:
        if self._node_completed(checkpoint, "finalize"):
            return checkpoint["node_outputs"]["finalize"]
        return await self._complete_node(checkpoint, "finalize", dict(planner_output), emit_step)

    async def run_chat(
        self,
        session_id: str,
        message: str,
        checkpoint: dict | None = None,
        emit_step: EmitStep | None = None,
    ) -> dict:
        latest_checkpoint = self._normalize_checkpoint(checkpoint)
        ingest_output = await self._run_ingest(session_id, message, latest_checkpoint, emit_step)
        planner_output = await self._run_planner(ingest_output, latest_checkpoint, emit_step)
        final_output = await self._run_finalize(planner_output, latest_checkpoint, emit_step)
        result = dict(final_output)
        result["checkpoint"] = self._checkpoint_snapshot(latest_checkpoint)
        return result
