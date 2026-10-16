"""
Shared test fixtures.

state_persistence.py backs search_state (plan, candidates, chat sessions) in
MongoDB Atlas now (was a local JSON file) — see its own module docstring for
why. Without this fixture, every test that touches a state-mutating
/search endpoint makes a REAL network round-trip to Atlas on every save,
which turned the suite from ~2s to ~100s and made it depend on live Atlas
connectivity to even run. Autouse + session-scoped so it's in effect for
the entire suite by default; no individual test file needs to opt in.

This intentionally does NOT test state_persistence's actual MongoDB
read/write correctness — that's covered separately (see test_preference_service.py's
FakeCollection pattern, which this mirrors) if/when dedicated persistence
tests are added. This fixture's only job is keeping the rest of the suite
fast and hermetic.
"""
import pytest

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services import state_persistence

_fake_store = {}


def _fake_load_state():
    return dict(_fake_store)


def _fake_save_state(**kwargs):
    _fake_store.clear()
    _fake_store.update(kwargs)


@pytest.fixture(autouse=True)
def _in_memory_state_persistence(monkeypatch):
    monkeypatch.setattr(state_persistence, "load_state", _fake_load_state)
    monkeypatch.setattr(state_persistence, "save_state", _fake_save_state)
    yield
