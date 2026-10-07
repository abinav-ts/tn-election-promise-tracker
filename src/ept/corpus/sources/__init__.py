"""Source adapter registry (spec 01 §2.3)."""

from __future__ import annotations

from ept.corpus.sources.base import SourceAdapter
from ept.corpus.sources.tn_policy_notes import TnPolicyNotes

ADAPTERS: dict[str, type[SourceAdapter]] = {
    a.name: a for a in [TnPolicyNotes]
}
