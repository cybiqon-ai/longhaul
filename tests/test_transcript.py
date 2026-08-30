"""Reading a stored run back as a conversation.

The difference between a ledger row saying $1.99 and being able to see what was
actually asked and done for it.
"""

import json

from longhaul.core import transcript


def write(path, *events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def assistant(*blocks):
    return {"type": "assistant", "message": {"content": list(blocks)}}


RESULT = {
    "type": "result", "subtype": "success", "is_error": False,
    "result": "done", "session_id": "s1", "total_cost_usd": 1.99,
    "duration_ms": 592300, "num_turns": 14,
}


def test_a_missing_file_is_an_empty_transcript(tmp_path):
    t = transcript.read(tmp_path / "nope.jsonl")
    assert t.messages == [] and t.cost_usd == 0


def test_it_reads_text_and_the_result_metadata(tmp_path):
    path = write(tmp_path / "r.jsonl",
                 assistant({"type": "text", "text": "I will scaffold the app."}), RESULT)
    t = transcript.read(path)
    assert t.messages[0].role == "assistant"
    assert "scaffold the app" in t.messages[0].text
    assert (t.session_id, t.cost_usd, t.num_turns) == ("s1", 1.99, 14)
    assert t.ok


def test_tool_calls_and_results_are_kept_separate_from_prose(tmp_path):
    path = write(
        tmp_path / "r.jsonl",
        assistant({"type": "text", "text": "Running the tests."},
                  {"type": "tool_use", "name": "Bash", "input": {"command": "flutter test"}}),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "214 passed"}]}},
        RESULT)
    t = transcript.read(path)
    call = t.messages[0].tools[0]
    assert call["kind"] == "call" and call["name"] == "Bash"
    assert "flutter test" in call["input"]
    assert t.messages[1].tools[0]["kind"] == "result"
    assert t.tools_used == ["Bash"]


def test_thinking_is_shown_rather_than_dropped(tmp_path):
    path = write(tmp_path / "r.jsonl",
                 assistant({"type": "thinking", "thinking": "the engine must stay pure"}), RESULT)
    assert "engine must stay pure" in transcript.read(path).messages[0].text


def test_a_failed_tool_result_is_marked(tmp_path):
    path = write(tmp_path / "r.jsonl",
                 {"type": "user", "message": {"content": [
                     {"type": "tool_result", "content": "boom", "is_error": True}]}}, RESULT)
    assert transcript.read(path).messages[0].tools[0]["error"] is True


def test_subagent_messages_are_marked(tmp_path):
    event = {**assistant({"type": "text", "text": "sub"}), "parent_tool_use_id": "tu_1"}
    path = write(tmp_path / "r.jsonl", event, RESULT)
    assert transcript.read(path).messages[0].to_dict()["subagent"] is True


def test_api_retries_are_surfaced(tmp_path):
    path = write(tmp_path / "r.jsonl",
                 {"type": "system", "subtype": "api_retry", "error": "rate_limit"},
                 {"type": "system", "subtype": "api_retry", "error": "overloaded"}, RESULT)
    assert transcript.read(path).retries == ["rate_limit", "overloaded"]


def test_credentials_never_survive_into_a_transcript(tmp_path):
    """Agent output reaches the browser from here."""
    token = "ghp_" + "A" * 36
    path = write(tmp_path / "r.jsonl",
                 assistant({"type": "text", "text": f"pushing with {token}"}), RESULT)
    body = json.dumps(transcript.read(path).to_dict())
    assert token not in body
    assert "redacted" in body


def test_a_huge_tool_result_is_clipped_for_display(tmp_path):
    path = write(tmp_path / "r.jsonl",
                 {"type": "user", "message": {"content": [
                     {"type": "tool_result", "content": "x" * 20000}]}}, RESULT)
    shown = transcript.read(path).messages[0].tools[0]["input"]
    assert len(shown) < 6000
    assert "more characters on disk" in shown, "it must say the full text is still there"


def test_non_json_and_torn_lines_do_not_lose_the_rest(tmp_path):
    path = tmp_path / "r.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "Warning: no stdin data received\n"
        + json.dumps(assistant({"type": "text", "text": "kept"})) + "\n"
        + json.dumps(RESULT) + "\n"
        + '{"type": "assis'
    )
    t = transcript.read(path)
    assert t.messages[0].text == "kept"
    assert t.session_id == "s1"


def test_the_path_encodes_day_task_role_and_attempt(tmp_path):
    p = transcript.path_for(tmp_path, 7, "t9", "coder", 2)
    assert p.relative_to(tmp_path).as_posix() == ".longhaul/runs/day-07/t9/coder-2.jsonl"


def test_the_index_lists_what_is_on_disk(tmp_path):
    write(transcript.path_for(tmp_path, 1, "t1", "coder", 1), RESULT)
    write(transcript.path_for(tmp_path, 3, "t5", "designer", 2), RESULT)
    rows = transcript.index(tmp_path)
    assert {(r["day"], r["task"], r["role"], r["attempt"]) for r in rows} == {
        (1, "t1", "coder", 1), (3, "t5", "designer", 2)}
    assert all(r["size"] > 0 for r in rows)


def test_the_index_of_nothing_is_empty(tmp_path):
    assert transcript.index(tmp_path) == []
