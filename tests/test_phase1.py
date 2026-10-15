"""Phase 1 tests: replay equality, compaction safety, malformed calls, resume, store rewrite."""
from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.tools import tool
from rich.console import Console

from momo.cli.animation import ThinkingAnimation, format_tokens
from momo.cli.commands import CommandRegistry, register_builtin_commands
from momo.cli.renderer import Renderer
from momo.core.compactor import Compactor, TokenTracker
from momo.core.events import EventType
from momo.core.harness import Harness
from momo.core.settings import Settings
from momo.store.sessions import SessionStore
from momo.tools.registry import ToolContext, ToolRegistry


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


class ScriptedModel:
    """Streams pre-scripted AIMessages in order (list is shared, not copied).

    Mimics ChatOllama: content arrives in pieces, tool calls and the token counts
    arrive on the final chunk.
    """
    def __init__(self, replies): self.replies = replies; self.calls = []
    def stream(self, messages):
        self.calls.append(messages)
        reply = self.replies.pop(0)
        text = reply.content
        half = len(text) // 2
        for piece in (text[:half], text[half:]):
            if piece:
                yield AIMessageChunk(content=piece)
        yield AIMessageChunk(content="", tool_calls=reply.tool_calls, response_metadata=reply.response_metadata)


class ConstModel:
    def __init__(self, text): self.text = text
    def invoke(self, messages): return AIMessage(content=self.text)


class FakeFactory:
    def __init__(self, replies, summary="SUMMARY"):
        self.replies, self.summary = replies, summary
    def build(self, spec, tools):
        return ScriptedModel(self.replies) if tools else ConstModel(self.summary)


def call(name, args, id_="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_, "type": "tool_call"}],
                     response_metadata={"prompt_eval_count": 100, "eval_count": 10})


def final(text):
    return AIMessage(content=text, response_metadata={"prompt_eval_count": 120, "eval_count": 12})


def make_console():
    buf = io.StringIO()
    return Console(file=buf, width=80, force_terminal=False, color_system=None), buf


def make_harness(tmp_path, replies, animation=None, **settings_over):
    console, buf = make_console()
    settings = Settings(project_root=tmp_path, db_path=tmp_path / "s.db", **settings_over)
    registry = ToolRegistry(); registry.register(add)
    commands = CommandRegistry(); register_builtin_commands(commands)
    harness = Harness(settings, registry, SessionStore(settings.db_path), Renderer(console), commands,
                      model_factory=FakeFactory(replies),
                      tool_context=ToolContext(tmp_path, ""), animation=animation)
    return harness, buf


def test_turn_persists_and_replay_matches_live(tmp_path):
    harness, live_buf = make_harness(tmp_path, [call("add", {"a": 2, "b": 3}), final("The answer is 5.")])
    session = harness.new_session()
    harness.handle(session, "what is 2+3")

    msgs = harness.store.load_messages(session.id)
    assert [type(m).__name__ for m in msgs] == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert msgs[2].content == "5"

    types = [e.type for e in harness.store.load_events(session.id)]
    assert types[0] == EventType.USER_MESSAGE and types[-1] == EventType.TURN_END
    assert EventType.TOOL_CALL in types and EventType.TOOL_RESULT in types

    replay_console, replay_buf = make_console()
    harness.renderer = Renderer(replay_console)
    harness.replay(session)
    replay_lines = replay_buf.getvalue().splitlines()
    assert replay_lines[0].startswith("› what is 2+3")      # replay echoes the user line
    # your renderer prints a blank line after a replayed user message; live mode does not
    assert replay_lines[2:] == live_buf.getvalue().splitlines()


def test_malformed_args_become_error_tool_message(tmp_path):
    harness, _ = make_harness(tmp_path, [call("add", {"a": "x", "b": 1}), final("sorry")])
    session = harness.new_session()
    harness.handle(session, "go")
    msgs = harness.store.load_messages(session.id)
    tool_msgs = [m for m in msgs if isinstance(m, ToolMessage)]
    assert tool_msgs and tool_msgs[0].status == "error"
    assert "Invalid arguments" in tool_msgs[0].content
    assert isinstance(msgs[-1], AIMessage) and msgs[-1].content == "sorry"


def test_unknown_tool_is_reported_not_raised(tmp_path):
    harness, _ = make_harness(tmp_path, [call("nope", {}), final("ok")])
    session = harness.new_session()
    harness.handle(session, "go")
    err = [m for m in harness.store.load_messages(session.id) if isinstance(m, ToolMessage)][0]
    assert "Unknown tool 'nope'" in err.content and "add" in err.content


def test_malformed_streak_ends_the_turn(tmp_path):
    bad = [call("add", {"a": "x", "b": 1}, f"c{i}") for i in range(3)]
    harness, _ = make_harness(tmp_path, bad)      # a 4th model call would raise IndexError
    session = harness.new_session()
    harness.handle(session, "go")
    errors = [e for e in harness.store.load_events(session.id) if e.type == EventType.ERROR]
    assert errors and "malformed" in errors[-1].payload["message"]


def test_max_iterations_stops_without_dangling_tool_calls(tmp_path):
    replies = [call("add", {"a": 1, "b": 1}, f"c{i}") for i in range(5)]
    harness, _ = make_harness(tmp_path, replies, max_iterations=2)
    session = harness.new_session()
    harness.handle(session, "loop")
    msgs = harness.store.load_messages(session.id)
    assert isinstance(msgs[-1], ToolMessage)       # history ends valid


def _pairs_messages(n_pairs):
    msgs = [HumanMessage(content="start", id="h0")]
    for i in range(n_pairs):
        msgs.append(AIMessage(content="", id=f"a{i}", tool_calls=[{"name": "add", "args": {"a": 1, "b": 1}, "id": f"t{i}", "type": "tool_call"}]))
        msgs.append(ToolMessage(content="2", tool_call_id=f"t{i}", name="add", id=f"r{i}"))
    return msgs


@pytest.mark.parametrize("keep", [1, 2, 3, 4])
def test_compaction_never_splits_tool_pairs(keep):
    msgs = _pairs_messages(4)
    compactor = Compactor(ConstModel("S"), TokenTracker(max_context=10), keep_recent=keep)
    result = compactor.compact(msgs)
    assert result.compacted
    new = result.messages
    assert new[0].additional_kwargs.get("momo_summary")
    assert not isinstance(new[1], ToolMessage)                     # recent never starts with a tool reply
    ai_calls = {c["id"] for m in new if isinstance(m, AIMessage) for c in m.tool_calls}
    replies = {m.tool_call_id for m in new if isinstance(m, ToolMessage)}
    assert replies <= ai_calls                                      # every kept reply keeps its call


def test_compaction_noop_when_nothing_safe():
    msgs = [HumanMessage(content="hi", id="h")]
    result = Compactor(ConstModel("S"), TokenTracker(max_context=10), keep_recent=6).compact(msgs)
    assert not result.compacted and result.messages == msgs


def test_tracker_uses_estimate_on_resume_then_real_counts():
    tracker = TokenTracker(max_context=1000)
    big = [HumanMessage(content="x" * 5000)]              # ~1430 estimated tokens, no real count yet
    assert tracker.needs_compaction(big)
    msgs = [HumanMessage(content="hi"), AIMessage(content="ok")]
    tracker.update_turn({"prompt_eval_count": 3000, "eval_count": 50}, index=1)
    assert tracker.current_tokens(msgs) == 3050
    assert tracker.current_tokens(msgs + [ToolMessage(content="x" * 350, tool_call_id="t")]) > 3050
    tracker.reset()
    assert not tracker.needs_compaction([HumanMessage(content="hi")])


def test_compaction_triggers_when_last_message_is_tool_result():
    # the case that crashed: the compact node runs after a ToolMessage, which has no counts
    tracker = TokenTracker(max_context=1000)
    msgs = [HumanMessage(content="go"),
            AIMessage(content="", id="a", tool_calls=[{"name": "t", "args": {}, "id": "1", "type": "tool_call"}]),
            ToolMessage(content="ok", tool_call_id="1")]
    tracker.update_turn({"prompt_eval_count": 1200, "eval_count": 9}, index=1)
    assert tracker.needs_compaction(msgs)                  # 1200 + 9 + estimate(tool result) > 1000


def test_compaction_reset_drops_stale_anchor():
    tracker = TokenTracker(max_context=1000)
    msgs = [HumanMessage(content="go"), AIMessage(content="ok")]
    tracker.update_turn({"prompt_eval_count": 5000, "eval_count": 5}, index=1)
    assert tracker.needs_compaction(msgs)
    tracker.reset()
    assert not tracker.needs_compaction(msgs)              # the old 5000 no longer applies


def test_auto_compaction_in_turn_and_store_rewrite(tmp_path):
    # tiny threshold forces compaction before the second model call
    replies = [call("add", {"a": 1, "b": 1}, "c1"), final("done")]
    harness, _ = make_harness(tmp_path, replies, max_context_tokens=60, keep_recent_messages=2)
    session = harness.new_session()
    harness.store.replace_messages(session.id, [HumanMessage(content="old " * 200), AIMessage(content="older " * 200)])
    harness.handle(session, "go")

    events = list(harness.store.load_events(session.id))
    assert any(e.type == EventType.COMPACTION for e in events)
    active = harness.store.load_messages(session.id)
    assert active[0].additional_kwargs.get("momo_summary")
    n_compacted = harness.store.conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id=? AND compacted=1", (session.id,)).fetchone()[0]
    assert n_compacted > 0
    ids = [m.id for m in active]
    assert len(ids) == len(set(ids))


def test_replace_messages_pure_append_inserts_only_tail(tmp_path):
    harness, _ = make_harness(tmp_path, [])
    session = harness.new_session()
    m1 = [HumanMessage(content="a"), AIMessage(content="b")]
    harness.store.replace_messages(session.id, m1)
    harness.store.replace_messages(session.id, m1 + [HumanMessage(content="c")])
    rows = harness.store.conn.execute("SELECT COUNT(*) FROM messages WHERE session_id=?", (session.id,)).fetchone()[0]
    assert rows == 3


def test_slash_commands(tmp_path):
    harness, buf = make_harness(tmp_path, [final("hi")])
    session = harness.new_session()
    harness.handle(session, "hello")
    s2 = harness.handle(session, "/clear")
    assert s2.id != session.id and harness.session.id == s2.id
    s3 = harness.handle(s2, f"/resume {session.id[:6]}")
    assert s3.id == session.id
    harness.handle(s3, "/nope")
    assert "Unknown command" in buf.getvalue()


# ---------------------------------------------------------------- streaming + animation
def test_progress_reports_exact_token_count(tmp_path):
    harness, _ = make_harness(tmp_path, [final("The answer is five.")])   # eval_count = 12
    seen = []
    agent = harness._build_agent(harness.new_session().spec)
    agent.on_progress = seen.append
    list(agent.run([], "hi"))
    assert sum(seen) == 12                       # per-chunk +1s corrected to Ollama's eval_count
    assert agent.messages[-1].response_metadata["eval_count"] == 12
    assert type(agent.messages[-1]) is AIMessage  # stored as a plain AIMessage, not a chunk


def test_streamed_tool_calls_survive_aggregation(tmp_path):
    harness, _ = make_harness(tmp_path, [call("add", {"a": 2, "b": 3}), final("5")])
    session = harness.new_session()
    harness.handle(session, "go")
    ai = [m for m in harness.store.load_messages(session.id) if isinstance(m, AIMessage)][0]
    assert ai.tool_calls[0]["name"] == "add" and ai.tool_calls[0]["args"] == {"a": 2, "b": 3}


def test_format_tokens():
    assert format_tokens(0) == "0" and format_tokens(999) == "999"
    assert format_tokens(1500) == "1.5k" and format_tokens(12_345) == "12.3k"


def test_animation_draws_counter_and_clears_its_line():
    buf = io.StringIO()
    anim = ThinkingAnimation(stream=buf, enabled=True, speed=100, first_frame_delay=0.0, ascii_only=True)
    anim.start(); anim.start()                   # second start is a no-op
    anim.add_tokens(1500)
    time.sleep(0.15)
    anim.stop(); anim.stop()                     # second stop is a no-op
    out = buf.getvalue()
    assert "1.5k tokens" in out and out.endswith("\r\033[2K")
    anim.add_tokens(-9999)
    assert anim.tokens == 0                      # never negative


def test_animation_is_silent_when_disabled_or_never_drawn():
    buf = io.StringIO()
    off = ThinkingAnimation(stream=buf, enabled=False)
    off.start(); off.add_tokens(5); off.stop()
    quick = ThinkingAnimation(stream=buf, enabled=True, first_frame_delay=5)
    quick.start(); quick.stop()                  # stopped before the first frame: nothing to clear
    assert buf.getvalue() == "" and off.tokens == 5


def test_harness_runs_spinner_only_during_the_turn(tmp_path):
    spinner_buf = io.StringIO()
    anim = ThinkingAnimation(stream=spinner_buf, enabled=True, first_frame_delay=0.0, ascii_only=True)
    harness, render_buf = make_harness(tmp_path, [call("add", {"a": 1, "b": 1}), final("done")], animation=anim)
    session = harness.new_session()
    harness.handle(session, "go")
    assert anim._thread is None                  # stopped at TURN_END
    assert anim.tokens == 22                     # 10 + 12 from the two scripted generations
    assert "\r" not in render_buf.getvalue()    # spinner output never leaks into rendered text

    # /compact outside a turn must not leave a spinner running
    harness.handle(session, "/compact")
    assert anim._thread is None
