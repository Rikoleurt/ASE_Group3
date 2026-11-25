"""Mentions of catalogue signs (@[AB81 (ku)](sign:AB81)) in community comments."""
import pytest

from backend.app import mentions
from backend.app.data_controller import correction_data_controller
from backend.app.model.correction import CatalogueSign


@pytest.fixture(autouse=True)
def catalogue(monkeypatch):
    monkeypatch.setattr(correction_data_controller, "catalogue", lambda: [
        CatalogueSign(sign="AB01", name="AB01 (da)", glyph=None, reading="da", preview_url="/glyphs/AB01/preview.png"),
        CatalogueSign(sign="AB81", name="AB81 (ku)", glyph=None, reading="ku", preview_url="/glyphs/AB81/preview.png")])


def test_sign_tokens_are_parsed_alongside_users_and_symbols():
    refs = mentions.parse_mentions("@[AB81 (ku)](sign:AB81), @[bob](user:3) and @[ka](symbol:12:4)")
    assert [(ref.kind, ref.key, ref.sign_code) for ref in refs] == [
        ("sign", "sign:AB81", "AB81"), ("user", "user:3", None), ("symbol", "symbol:12:4", None)]
    assert mentions.parse_mentions("@[x](sign:AB81!)") == []  # only letters and digits
    assert mentions.parse_mentions("@[x](sign:" + "A" * 13 + ")") == []


def test_signs_resolve_from_the_catalogue_in_any_spelling():
    [resolved] = mentions.resolve_mentions(None, ["@[ku](sign:AB81) @[da](sign:ab1) @[?](sign:ZZ9)"])
    ku, da, unknown = resolved
    assert (ku.kind, ku.label, ku.sign_code, ku.image_url, ku.available) == (
        "sign", "AB81 (ku)", "AB81", "/api/glyphs/AB81/preview.png", True)
    assert (da.sign_code, da.label, da.key) == ("AB01", "AB01 (da)", "sign:ab1")  # the token's own key is kept
    assert (unknown.available, unknown.sign_code, unknown.label) == (False, "ZZ9", "?")


def test_a_comment_cannot_mention_a_sign_outside_the_catalogue():
    assert [m.sign_code for m in mentions.validate_mentions(None, "is it @[ku](sign:AB81)?")] == ["AB81"]
    with pytest.raises(mentions.InvalidMention, match="sign is no longer available"):
        mentions.validate_mentions(None, "@[?](sign:ZZ9)")
