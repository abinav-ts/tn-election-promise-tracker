"""Frozen terms (spec 02 §4.9, D-039): every extract step refuses to re-extract them."""

from __future__ import annotations

from ept.config import Config


class FrozenTermError(RuntimeError):
    pass


def is_frozen(cfg: Config, term_id: str) -> bool:
    return term_id in cfg.settings.extract.frozen_terms


def check_writable(cfg: Config, term_id: str, step: str) -> None:
    """Raise if `step` would rewrite a frozen term's outputs (`--force` included)."""
    if is_frozen(cfg, term_id):
        raise FrozenTermError(
            f"{term_id} is frozen (data/frozen/promises_{term_id}.jsonl); `extract {step}` refuses to touch it. "
            "Un-freezing needs a decision-log entry (spec 02 §4.9)."
        )
