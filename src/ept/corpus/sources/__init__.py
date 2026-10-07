"""Source adapter registry (spec 01 §2.3)."""

from __future__ import annotations

from ept.corpus.sources.base import SourceAdapter
from ept.corpus.sources.cag_reports import CagReports
from ept.corpus.sources.tn_policy_notes import TnPolicyNotes
from ept.corpus.sources.tn_schemes import TnSchemes
from ept.corpus.sources.tnbudget_speeches import TnBudgetSpeeches

ADAPTERS: dict[str, type[SourceAdapter]] = {
    a.name: a for a in [TnPolicyNotes, TnBudgetSpeeches, CagReports, TnSchemes]
}
