from flipperbot.messages import message, offer


def row(**kw):
    base = {"title": "Nikon FE + Nikkor 70-210", "price_ron": 500, "est_value_ron": 800, "niche": "cameras", "score": 7, "ai": None}
    base.update(kw)
    return base


class Row(dict):
    def keys(self):
        return super().keys()


def test_offer_leaves_a_margin_but_is_never_insulting():
    assert offer(Row(row()), None) == 450  # plenty of margin already: still haggle 10%
    assert offer(Row(row(price_ron=900)), None) == 650  # margin under the realistic sale
    assert offer(Row(row(price_ron=2000, est_value_ron=1300)), None) == 1200  # never under 60% of asking
    assert offer(Row(row()), {"offer_ron": 420}) == 420  # Claude's offer wins


def test_message_in_romanian_with_the_right_questions():
    m = message(Row(row(price_ron=900)), None)
    assert m.startswith("Bună ziua! Mai este disponibil anunțul „Nikon FE + Nikkor 70-210”?")
    assert "declanșatorul" in m and "650 lei" in m and m.endswith("Mulțumesc!")
    phone = message(Row(row(niche="phones", title="iPhone 13 128GB", price_ron=1500, est_value_ron=1200)), None)
    assert "iCloud" in phone
    claude = message(Row(row()), {"questions_for_seller": ["Merge exponometrul cu baterie nouă?"], "offer_ron": 420})
    assert "exponometrul" in claude and "420 lei" in claude
