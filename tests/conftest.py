import pytest


@pytest.fixture(autouse=True)
def no_real_claude(monkeypatch, request):
    """Tests never call the real Claude: the quick AI step is a no-op unless a test asks for it."""
    if "real_quick" in request.keywords:
        return
    from flipperbot import quick

    monkeypatch.setattr(quick, "run", lambda *a, **k: 0)
