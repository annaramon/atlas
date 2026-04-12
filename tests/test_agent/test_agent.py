import json
from unittest.mock import MagicMock, patch

import pytest

from app.agent.agent import ask


def _make_response(content: str, tool_calls: list = None) -> MagicMock:
    """Build a fake ollama.chat() response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    response = MagicMock()
    response.message = msg
    return response


def _make_tool_call(name: str, arguments: dict) -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    call = MagicMock()
    call.function = fn
    return call


# ---------------------------------------------------------------------------
# No tool calls
# ---------------------------------------------------------------------------

def test_ask_returns_content_when_no_tool_calls():
    with patch("app.agent.agent.ollama.chat", return_value=_make_response("Here is your answer.")):
        result = ask("How did I sleep last night?")
    assert result == "Here is your answer."


# ---------------------------------------------------------------------------
# Tool call dispatched and loop continues
# ---------------------------------------------------------------------------

def test_ask_dispatches_tool_and_returns_final_content():
    tool_result = [{"date": "2026-03-10", "balance": 0.8}]
    tool_call = _make_tool_call("get_recovery_summary", {"start_date": "2026-03-10", "end_date": "2026-03-10"})

    first_response = _make_response("", tool_calls=[tool_call])
    second_response = _make_response("Your recovery balance was 0.8.")

    call_count = {"n": 0}

    def fake_chat(**kwargs):
        call_count["n"] += 1
        return first_response if call_count["n"] == 1 else second_response

    with (
        patch("app.agent.agent.ollama.chat", side_effect=fake_chat),
        patch("app.agent.agent.TOOL_DISPATCH", {"get_recovery_summary": lambda **kw: tool_result}),
    ):
        result = ask("How was my recovery?")

    assert result == "Your recovery balance was 0.8."
    assert call_count["n"] == 2


def test_ask_tool_result_is_json_in_messages():
    """The tool result appended to messages must be JSON-serialisable."""
    tool_result = {"hr_max": 198}
    tool_call = _make_tool_call("get_user_profile", {})

    captured_messages = []

    def fake_chat(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        if len(captured_messages) <= 2:
            return _make_response("", tool_calls=[tool_call])
        return _make_response("Done.")

    with (
        patch("app.agent.agent.ollama.chat", side_effect=fake_chat),
        patch("app.agent.agent.TOOL_DISPATCH", {"get_user_profile": lambda **kw: tool_result}),
    ):
        ask("What is my hr max?")

    tool_messages = [m for m in captured_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_messages) == 1
    parsed = json.loads(tool_messages[0]["content"])
    assert parsed == {"hr_max": 198}


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

def test_ask_unknown_tool_returns_error_and_continues():
    tool_call = _make_tool_call("nonexistent_tool", {})

    call_count = {"n": 0}

    def fake_chat(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_response("", tool_calls=[tool_call])
        # Verify the error was passed back — model responds after seeing it
        last = kwargs["messages"][-1]
        assert "Unknown tool" in last["content"]
        return _make_response("I could not find that tool.")

    with patch("app.agent.agent.ollama.chat", side_effect=fake_chat):
        result = ask("Call a fake tool.")

    assert result == "I could not find that tool."


# ---------------------------------------------------------------------------
# Tool raises exception
# ---------------------------------------------------------------------------

def test_ask_tool_exception_sends_error_and_continues():
    tool_call = _make_tool_call("get_workout_summary", {"start_date": "bad", "end_date": "bad"})

    call_count = {"n": 0}

    def fake_chat(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_response("", tool_calls=[tool_call])
        last = kwargs["messages"][-1]
        assert "error" in json.loads(last["content"])
        return _make_response("There was an error.")

    def exploding_tool(**kwargs):
        raise ValueError("Invalid date format")

    with (
        patch("app.agent.agent.ollama.chat", side_effect=fake_chat),
        patch("app.agent.agent.TOOL_DISPATCH", {"get_workout_summary": exploding_tool}),
    ):
        result = ask("Show me workouts.")

    assert result == "There was an error."
