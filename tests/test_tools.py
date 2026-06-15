import tools
from tools import create_fit_card, search_listings, suggest_outfit


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]


class _FakeCompletions:
    def __init__(self, content: str):
        self._content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._content)


class _FakeClient:
    def __init__(self, content: str):
        self.chat = type("Chat", (), {"completions": _FakeCompletions(content)})()


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(item["price"] <= 50 for item in results)


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("graphic tee", size=None, max_price=20)
    assert results
    assert all(item["price"] <= 20 for item in results)


def test_suggest_outfit_empty_wardrobe_returns_advice(monkeypatch):
    fake_client = _FakeClient("Try pairing it with sleek basics and chunky shoes.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    result = suggest_outfit(
        new_item={
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "style_tags": ["vintage", "graphic tee"],
            "colors": ["black"],
            "condition": "good",
            "price": 24,
            "platform": "depop",
        },
        wardrobe={"items": []},
    )

    assert isinstance(result, str)
    assert result == "Try pairing it with sleek basics and chunky shoes."
    call = fake_client.chat.completions.calls[0]
    assert "general styling advice" in call["messages"][1]["content"]


def test_suggest_outfit_uses_wardrobe_items(monkeypatch):
    fake_client = _FakeClient("Wear it with the wide-leg trousers and layer the jacket on top.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    result = suggest_outfit(
        new_item={
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "style_tags": ["vintage", "graphic tee"],
            "colors": ["black"],
            "condition": "good",
            "price": 24,
            "platform": "depop",
        },
        wardrobe={
            "items": [
                {
                    "id": "w_001",
                    "name": "Baggy straight-leg jeans",
                    "category": "bottoms",
                    "colors": ["dark blue"],
                    "style_tags": ["baggy"],
                    "notes": None,
                }
            ]
        },
    )

    assert result == "Wear it with the wide-leg trousers and layer the jacket on top."
    call = fake_client.chat.completions.calls[0]
    assert "Baggy straight-leg jeans" in call["messages"][1]["content"]


def test_create_fit_card_requires_outfit():
    result = create_fit_card("   ", {"title": "Vintage Graphic Tee"})
    assert result.startswith("Error: outfit suggestion is missing")


def test_create_fit_card_returns_caption(monkeypatch):
    fake_client = _FakeClient("thrifted this tee and styled it with my baggy jeans, easy win")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    result = create_fit_card(
        outfit="Wear it with baggy jeans and chunky sneakers.",
        new_item={
            "title": "Vintage Graphic Tee",
            "price": 24,
            "platform": "depop",
        },
    )

    assert result == "thrifted this tee and styled it with my baggy jeans, easy win"
    call = fake_client.chat.completions.calls[0]
    assert "Vintage Graphic Tee" in call["messages"][1]["content"]
    assert call["temperature"] > 1.0
