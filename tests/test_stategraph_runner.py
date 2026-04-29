from types import SimpleNamespace

import pytest

from app.orchestration.stategraph_runner import StateGraphRunner


@pytest.mark.asyncio
async def test_runner_uses_checkpoint_to_skip_completed_nodes():
    class RecordingChatService:
        def __init__(self) -> None:
            self.messages: list[str] = []

        async def process_message(self, request):
            self.messages.append(request.message)
            return SimpleNamespace(
                session_id=request.session_id,
                response="planner should have been skipped",
                updated_plan={"transport_plan": "unexpected"},
                pending_questions=[],
            )

    chat_service = RecordingChatService()
    runner = StateGraphRunner(chat_service=chat_service)
    emitted: list[tuple[str, dict]] = []
    checkpoint = {
        "completed_nodes": ["ingest", "planner"],
        "node_outputs": {
            "ingest": {"session_id": "s-checkpoint", "message": "plan trip"},
            "planner": {
                "session_id": "s-checkpoint",
                "response": "from checkpoint",
                "updated_plan": {"hotel_plan": {"name": "cached hotel"}},
                "pending_questions": [],
                "needs_user_input": False,
            },
        },
    }

    result = await runner.run_chat(
        session_id="s-checkpoint",
        message="plan trip",
        checkpoint=checkpoint,
        emit_step=lambda node, output, latest_checkpoint: emitted.append((node, output)),
    )

    assert chat_service.messages == []
    assert [node for node, _output in emitted] == ["finalize"]
    assert result["response"] == "from checkpoint"
    assert result["updated_plan"] == {"hotel_plan": {"name": "cached hotel"}}
    assert result["checkpoint"]["completed_nodes"] == ["ingest", "planner", "finalize"]
    assert result["checkpoint"]["node_outputs"]["finalize"]["response"] == "from checkpoint"
