"""`ept extract backend-test` (spec 02 §4.8): the bulk model choice. `--smoke` = one live call (step 3)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ept.config import get_config
from ept.llm import LLMClient


class SmokeOut(BaseModel):
    ok: bool
    echo: str


def run_smoke(model: Optional[str] = None) -> dict[str, Any]:
    """One live call (cached afterwards) with no project data: checks key, model name, JSON mode."""
    cfg = get_config()
    model = model or cfg.settings.llm.models.get("vision")
    client = LLMClient(cfg)
    out = client.complete_json("smoke_test", {"word": "vanakkam"}, SmokeOut, model=model)
    return {"model": model, "ok": out.ok and out.echo == "vanakkam", "cache_hit": client.last.cache_hit,
            "seconds": client.last.seconds, "http_retries": client.last.http_retries}
