import pytest


@pytest.fixture(autouse=True)
def no_real_claude(monkeypatch, request):
    """Tests never call the real Claude: the quick AI step is a no-op unless a test asks for it."""
    if "real_quick" in request.keywords:
        return
    from flipperbot import quick

    monkeypatch.setattr(quick, "run", lambda *a, **k: 0)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never reach a real site (OLX, Publi24, eBay, Telegram...): every request goes through net.urlopen,
    and here it fails. A test that needs a site passes a stand-in instead."""
    from flipperbot import net

    def blocked(*a, **k):
        raise RuntimeError("a test tried to use the network")

    monkeypatch.setattr(net, "urlopen", blocked)
