"""Source adapter interface and shared helpers."""

from __future__ import annotations

import base64
import logging
from typing import Iterator, Optional

from ept.config import Config, SourceCfg
from ept.corpus.catalogue import CatalogueItem
from ept.corpus.wayback import Wayback
from ept.net import Http
from ept.runs import Budget

log = logging.getLogger(__name__)


def b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def unb64(value: str) -> str:
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


class SourceAdapter:
    """Yields CatalogueItems from official listings. Never downloads documents."""

    name: str = ""

    def __init__(self, cfg: Config, http: Http, wayback: Wayback):
        self.cfg = cfg
        self.http = http
        self.wayback = wayback
        self.scfg: SourceCfg = cfg.sources.sources[self.name]

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        raise NotImplementedError

    def department(self, dep_id: Optional[str], raw_name: Optional[str]) -> Optional[str]:
        """Canonical department name via the dep_id map in sources.yaml; unmapped names kept raw and logged."""
        if dep_id is not None and dep_id in self.cfg.sources.departments:
            return self.cfg.sources.departments[dep_id]
        if raw_name:
            log.warning("%s: unmapped department dep_id=%s name=%r kept raw", self.name, dep_id, raw_name)
            return " ".join(raw_name.split())
        return None
