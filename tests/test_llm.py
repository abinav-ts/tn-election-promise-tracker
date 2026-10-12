import json

import pytest
from pydantic import BaseModel

from ept.llm import LLMClient, LLMValidationError, PromptError, load_prompt


class Out(BaseModel):
    answer: str
    score: float


def _prompt(root, name, header="version: 1.0\n"):
    (root / "prompts" / f"{name}.md").write_text(header + "\nQuestion: {{q}}\n", encoding="utf-8")


def test_missing_version_header_raises(root):
    _prompt(root, "t_ok", header="title: no version\n")
    with pytest.raises(PromptError):
        load_prompt("t_ok")
    (root / "prompts" / "plain.md").write_text("No header at all {{q}}\n")
    with pytest.raises(PromptError):
        load_prompt("plain")


def test_prompt_header_and_render(root):
    _prompt(root, "t_ok", header="---\nversion: 2.1\nnote: x\n---\n")
    p = load_prompt("t_ok")
    assert p.version == "2.1"
    assert p.render({"q": "why"}).strip() == "Question: why"
    with pytest.raises(PromptError):
        p.render({})


def test_mock_returns_fixture(root):
    _prompt(root, "t_ok")
    out = LLMClient().complete_json("t_ok", {"q": "a"}, Out)
    assert out == Out(answer="yes", score=0.9)


def test_invalid_output_retries_once_then_errors(root):
    _prompt(root, "t_bad")
    client = LLMClient()
    with pytest.raises(LLMValidationError):
        client.complete_json("t_bad", {"q": "a"}, Out)
    assert client.calls == 2


def test_retry_recovers(root):
    _prompt(root, "t_retry")
    client = LLMClient()
    assert client.complete_json("t_retry", {"q": "a"}, Out).score == 0.5
    assert client.calls == 2


def test_cache_hit_avoids_second_call(root):
    _prompt(root, "t_ok")
    client = LLMClient()
    a = client.complete_json("t_ok", {"q": "a"}, Out)
    b = client.complete_json("t_ok", {"q": "a"}, Out)
    assert a == b and client.calls == 1
    client.complete_json("t_ok", {"q": "different"}, Out)
    assert client.calls == 2
    assert len(list((root / "cache" / "llm").glob("*.json"))) == 2


def test_usage_log_written(root):
    _prompt(root, "t_ok")
    client = LLMClient()
    client.complete_json("t_ok", {"q": "a"}, Out)
    client.complete_json("t_ok", {"q": "a"}, Out)
    lines = [json.loads(l) for l in (root / "reports" / "llm_usage.jsonl").read_text().splitlines()]
    assert [l["cache_hit"] for l in lines] == [False, True]
    assert lines[0]["prompt"] == "t_ok" and lines[0]["version"] == "1.0" and lines[0]["backend"] == "mock"


def test_unset_bulk_model_and_strong_stub(root, monkeypatch):
    _prompt(root, "t_ok")
    monkeypatch.setenv("EPT_LLM_MOCK", "0")
    with pytest.raises(ValueError, match="backend-test"):
        LLMClient().complete_json("t_ok", {"q": "a"}, Out, backend="bulk")
    with pytest.raises(NotImplementedError, match="handoff"):
        LLMClient().complete_json("t_ok", {"q": "a"}, Out, backend="strong")
