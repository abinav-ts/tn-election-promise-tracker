"""Spec 02 §7: `_bulk` with a fake Gemini client (no network, no key)."""

import json

import pytest
from pydantic import BaseModel

from ept.config import MissingSecret, get_secret
from ept.llm import Image, LLMClient, QuotaExhausted

SECRET = "AIza-test-secret-never-logged"


class Out(BaseModel):
    answer: str


def _api_error(code, message):
    from google.genai import errors

    return errors.ClientError(code, {"error": {"code": code, "message": message, "status": "X"}}) if code < 500 \
        else errors.ServerError(code, {"error": {"code": code, "message": message, "status": "X"}})


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    def generate_content(self, model, contents, config):
        self.requests.append({"model": model, "contents": contents, "config": config})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item

        class R:
            text = item
        return R()


class FakeGemini:
    def __init__(self, script):
        self.models = FakeModels(script)


@pytest.fixture
def live(root, monkeypatch):
    (root / "prompts" / "t_bulk.md").write_text("version: 1.0\n\nQ: {{q}}\n", encoding="utf-8")
    monkeypatch.setenv("EPT_LLM_MOCK", "0")
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    return root


def _client(script, sleeps=None):
    sleeps = sleeps if sleeps is not None else []
    return LLMClient(gemini_client=FakeGemini(script), sleep=sleeps.append)


def test_json_mode_temperature_schema_and_images(live):
    c = _client(['{"answer": "ok"}'])
    out = c.complete_json("t_bulk", {"q": "x"}, Out, model="m-test", images=[Image(b"\xff\xd8jpg", "image/jpeg")])
    assert out.answer == "ok"
    req = c._gemini.models.requests[0]
    assert req["model"] == "m-test"
    assert req["config"].response_mime_type == "application/json"
    assert req["config"].temperature == 0
    assert req["config"].response_json_schema["properties"]["answer"]["type"] == "string"
    assert req["contents"][0].inline_data.mime_type == "image/jpeg" and req["contents"][1].strip() == "Q: x"


def test_image_changes_cache_key(live):
    c = _client(['{"answer": "a"}', '{"answer": "b"}'])
    a = c.complete_json("t_bulk", {"q": "x"}, Out, model="m", images=[Image(b"1", "image/png")])
    b = c.complete_json("t_bulk", {"q": "x"}, Out, model="m", images=[Image(b"2", "image/png")])
    assert (a.answer, b.answer) == ("a", "b") and c.calls == 2


def test_429_backoff_not_a_validation_retry(live):
    from ept.config import get_config

    get_config().settings.llm.bulk.rpm = None  # isolate backoff sleeps from the throttle
    sleeps = []
    c = _client([_api_error(429, "Resource exhausted (per minute)"), _api_error(503, "overloaded"),
                 '{"answer": "ok"}'], sleeps)
    assert c.complete_json("t_bulk", {"q": "x"}, Out, model="m").answer == "ok"
    assert c.last.attempts == 1 and c.last.first_valid and c.last.http_retries == 2
    assert sleeps == [5, 10]  # llm.bulk.backoff_s, doubled
    log = [json.loads(l) for l in (live / "reports" / "llm_usage.jsonl").read_text().splitlines()]
    assert log[-1]["http_retries"] == 2 and log[-1]["attempts"] == 1


def test_daily_quota_stops_cleanly(live):
    c = _client([_api_error(429, "Quota exceeded for metric GenerateRequestsPerDayPerProjectPerModel-FreeTier")])
    with pytest.raises(QuotaExhausted):
        c.complete_json("t_bulk", {"q": "x"}, Out, model="m")
    assert not list((live / "cache" / "llm").glob("*.json")) if (live / "cache" / "llm").exists() else True


def test_rpd_limit_stops_before_calling(live, monkeypatch):
    from ept.config import get_config

    get_config().settings.llm.bulk.rpd = {"m": 1, "other": None}
    c = _client(['{"answer": "a"}', '{"answer": "b"}'])
    c.complete_json("t_bulk", {"q": "1"}, Out, model="m")
    with pytest.raises(QuotaExhausted):
        c.complete_json("t_bulk", {"q": "2"}, Out, model="m")
    assert len(c._gemini.models.requests) == 1
    c.complete_json("t_bulk", {"q": "2"}, Out, model="other")  # quotas are per model
    assert len(c._gemini.models.requests) == 2


def test_validation_retry_then_ok(live):
    c = _client(["not json", '{"answer": "ok"}'])
    assert c.complete_json("t_bulk", {"q": "x"}, Out, model="m").answer == "ok"
    assert c.last.attempts == 2 and not c.last.first_valid


def test_key_never_in_logs_cache_or_run_metadata(live):
    from ept.runs import finish_run, start_run

    run_id = start_run("t")
    _client(['{"answer": "ok"}']).complete_json("t_bulk", {"q": "x"}, Out, model="m")
    finish_run(run_id, {})
    for path in [*(live / "cache").rglob("*"), *(live / "reports").rglob("*")]:
        if path.is_file():
            assert SECRET not in path.read_text(encoding="utf-8"), path


def test_missing_key_names_dotenv(root, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingSecret, match=r"\.env"):
        get_secret("GEMINI_API_KEY")


def test_key_read_from_dotenv(root, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (root / ".env").write_text("# comment\nexport GEMINI_API_KEY='abc123'\n", encoding="utf-8")
    assert get_secret("GEMINI_API_KEY") == "abc123"


def test_rpm_throttle_spaces_calls(live):
    from ept.config import get_config

    get_config().settings.llm.bulk.rpm = 6  # one call per 10 s
    t = [100.0]
    sleeps = []
    c = LLMClient(gemini_client=FakeGemini(['{"answer": "a"}', '{"answer": "b"}']),
                  sleep=lambda s: (sleeps.append(s), t.__setitem__(0, t[0] + s)), clock=lambda: t[0])
    c.complete_json("t_bulk", {"q": "1"}, Out, model="m")
    c.complete_json("t_bulk", {"q": "2"}, Out, model="m")
    assert sleeps == [pytest.approx(10.0)]


def test_cache_hit_keeps_original_call_stats(live):
    c = _client(["not json", '{"answer": "ok"}'])
    c.complete_json("t_bulk", {"q": "x"}, Out, model="m")
    c.complete_json("t_bulk", {"q": "x"}, Out, model="m")
    assert c.last.cache_hit and c.last.attempts == 2 and not c.last.first_valid
