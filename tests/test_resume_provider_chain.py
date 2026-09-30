"""
Tests for GroqResumeAIProvider's multi-provider chain (NVIDIA NIM ->
OpenRouter -> Groq -> deterministic local parser), same priority pattern as
RequirementAgent's chain (see tests/test_search_plan_validation.py).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.ai_providers import GroqResumeAIProvider


def test_provider_chain_prioritizes_nvidia_then_openrouter_then_groq(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_NIM_KEY", "nvapi-test")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")

    provider = GroqResumeAIProvider(api_key="gsk-test")
    chain = provider._provider_chain()

    assert [c[0] for c in chain] == ["nvidia", "openrouter", "groq"]
    assert chain[0][1] == settings.NVIDIA_API_URL
    assert chain[0][3] == settings.NVIDIA_MODEL
    assert chain[0][5] is False  # response_format:json_object not confirmed for NVIDIA
    assert chain[1][1] == settings.OPENROUTER_API_URL
    assert chain[1][3] == settings.OPENROUTER_MODEL
    assert chain[1][5] is False
    assert chain[2][5] is True  # confirmed supported for Groq


def test_nvidia_gets_a_short_timeout_others_stay_generous(monkeypatch):
    """
    NVIDIA has been observed (production logs) timing out 100% of the time
    on this endpoint's larger resume-structuring prompt. Waiting the full 90s
    budget before falling through made every conversion feel hung. NVIDIA
    gets a short timeout so a dead provider fails fast; OpenRouter/Groq keep
    the generous budget a large resume may genuinely need to succeed.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_NIM_KEY", "nvapi-test")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")

    provider = GroqResumeAIProvider(api_key="gsk-test")
    chain = provider._provider_chain()

    timeouts = {c[0]: c[6] for c in chain}
    assert timeouts["nvidia"] < timeouts["openrouter"]
    assert timeouts["nvidia"] <= 30.0
    assert timeouts["openrouter"] == timeouts["groq"] == 90.0


def test_provider_chain_skips_providers_without_a_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_NIM_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)

    provider = GroqResumeAIProvider(api_key="gsk-test")
    chain = provider._provider_chain()
    assert [c[0] for c in chain] == ["groq"]


def test_provider_chain_empty_falls_back_to_deterministic_parser(monkeypatch):
    import asyncio
    from app.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_NIM_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)

    provider = GroqResumeAIProvider(api_key=None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)

    result = asyncio.run(provider.structure_resume(
        {"raw_text": "John Doe\nSUMMARY\nExperienced engineer.", "sections": [
            {"title": "SUMMARY", "content": "Experienced engineer."},
        ]},
        "John Doe\nSUMMARY\nExperienced engineer.",
    ))
    assert result.get("personal_information", {}).get("name") == "John Doe"
