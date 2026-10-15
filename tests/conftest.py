"""Offline test harness: sockets are blocked, the LLM is mocked, EPT_ROOT is a temp copy."""

from __future__ import annotations

import os
import re
import shutil
import socket
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"

os.environ["EPT_LLM_MOCK"] = "1"


class NetworkBlocked(RuntimeError):
    pass


def _blocked(*args, **kwargs):
    raise NetworkBlocked("network access is blocked in tests")


@pytest.fixture(autouse=True, scope="session")
def _no_network():
    mp = pytest.MonkeyPatch()
    mp.setattr(socket.socket, "connect", _blocked)
    mp.setattr(socket.socket, "connect_ex", _blocked)
    mp.setattr(socket, "create_connection", _blocked)
    mp.setattr(socket, "getaddrinfo", _blocked)
    yield
    mp.undo()


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    """A throwaway project root with the real config and the test fixtures."""
    shutil.copytree(REPO / "config", tmp_path / "config")
    # tests start with no frozen term (the real project has frozen its terms; tests freeze explicitly)
    settings = tmp_path / "config" / "settings.yaml"
    settings.write_text(re.sub(r"(?m)^(  frozen_terms: )\[.*?\]", r"\1[]", settings.read_text(encoding="utf-8")),
                        encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    shutil.copytree(FIXTURES, tmp_path / "tests" / "fixtures")
    monkeypatch.setenv("EPT_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def conn(root):
    from ept import db

    c = db.connect()
    db.init_schema(c)
    db.sync_terms(c)
    yield c
    c.close()
