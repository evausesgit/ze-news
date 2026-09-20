import builtins

import pytest

from scripts.telegram_login import ask_phone


def _answers(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr(builtins, "input", lambda _="": next(it))


def test_accepts_international_number(monkeypatch):
    _answers(monkeypatch, ["+33612345678"])
    assert ask_phone() == "+33612345678"


def test_cleans_spaces_and_separators(monkeypatch):
    _answers(monkeypatch, [" +33 6 12-34.56(78) "])
    assert ask_phone() == "+33612345678"


def test_redemande_si_vide_ou_invalide(monkeypatch, capsys):
    # Une saisie vide faisait planter Telethon sur un TypeError illisible.
    _answers(monkeypatch, ["", "abc", "+33612345678"])
    assert ask_phone() == "+33612345678"
    assert capsys.readouterr().out.count("invalide") == 2


def test_abandonne_proprement_si_entree_fermee(monkeypatch):
    def boom(_=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", boom)
    with pytest.raises(EOFError):
        ask_phone()
